"""Live diagnostics for an OpenAI-compatible endpoint ("Test koneksi").

`POST /api/models` only proves the endpoint *answers*; it says nothing about
whether a chat request with the configured model + key actually works — which
is the question the user has when the UI shows an error. This module replays the
three requests that matter and reports each one verbatim:

    1. GET  <base>/models                 — endpoint hidup? key diterima?
                                            nama model ada di daftar?
    2. POST <base>/chat/completions       — request non-streaming, bentuk yang
                                            persis sama dengan contoh `curl`
    3. POST <base>/chat/completions       — request streaming (yang dipakai app)

The result is a list of checks with the server's own status + body excerpt, so
a 401 (key salah), 404 (nama model tidak ada) dan 400 (payload ditolak) are
told apart instead of all looking like "error".
"""
from __future__ import annotations

import json
import time
from typing import Any

import httpx

from .openai_provider import error_hint
from .url_utils import chat_completions_url, models_url, normalize_openai_base_url

TIMEOUT = httpx.Timeout(connect=15.0, read=60.0, write=30.0, pool=15.0)
PROBE_MESSAGE = "Say hello in a creative way"
PROBE_MAX_TOKENS = 64


def _excerpt(text: str, limit: int = 400) -> str:
    text = (text or "").strip()
    return text if len(text) <= limit else text[:limit] + " …"


def _error_message(text: str) -> str:
    """Pull `error.message` out of a JSON error body when there is one."""
    try:
        data = json.loads(text)
    except ValueError:
        return ""
    if isinstance(data, dict):
        err = data.get("error")
        if isinstance(err, dict) and err.get("message"):
            return str(err["message"])
        if isinstance(err, str):
            return err
        if data.get("message"):
            return str(data["message"])
    return ""


async def probe_endpoint(base_url: str, api_key: str = "", model: str = "",
                         transport: httpx.AsyncBaseTransport | None = None,
                         timeout: httpx.Timeout | None = TIMEOUT) -> dict[str, Any]:
    """Run the three checks. Never raises — problems are returned as data."""
    base = normalize_openai_base_url(base_url)
    report: dict[str, Any] = {
        "ok": False, "base_url": base or None, "model": model or None,
        "models_url": None, "chat_url": None, "checks": [], "hint": None,
    }
    if not base:
        report["hint"] = "Base URL kosong — isi dulu endpoint-nya."
        return report

    report["models_url"] = models_url(base)
    report["chat_url"] = chat_completions_url(base)
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    else:
        report["checks"].append({
            "name": "API key", "ok": False, "status": None,
            "error": "tidak ada API key yang dikirim",
            "hint": "Isi API key bila endpoint membutuhkannya.",
        })

    models_listed: list[str] = []
    try:
        async with httpx.AsyncClient(timeout=timeout, transport=transport,
                                     follow_redirects=True) as client:
            # ---- 1. GET /models -------------------------------------------
            started = time.time()
            try:
                r = await client.get(report["models_url"], headers=headers)
                latency = round((time.time() - started) * 1000)
                if r.status_code == 200:
                    try:
                        payload = r.json()
                    except ValueError:
                        payload = None
                    if isinstance(payload, dict):
                        models_listed = [
                            str(m.get("id") or m.get("model") or m.get("name"))
                            for m in (payload.get("data") or payload.get("models") or [])
                            if isinstance(m, dict)
                        ] or [str(m) for m in (payload.get("data") or [])
                              if isinstance(m, str)]
                    elif isinstance(payload, list):
                        models_listed = [str(m) for m in payload]
                    report["checks"].append({
                        "name": f"GET {report['models_url']}", "ok": True,
                        "status": 200, "latency_ms": latency,
                        "detail": f"{len(models_listed)} model terdaftar",
                        "models": models_listed[:50],
                    })
                else:
                    report["checks"].append({
                        "name": f"GET {report['models_url']}", "ok": False,
                        "status": r.status_code, "latency_ms": latency,
                        "error": _error_message(r.text) or _excerpt(r.text),
                        "hint": error_hint(r.status_code, r.text),
                    })
            except httpx.HTTPError as exc:
                report["checks"].append({
                    "name": f"GET {report['models_url']}", "ok": False,
                    "status": None, "error": f"{type(exc).__name__}: {exc}",
                    "hint": ("Endpoint tidak bisa dihubungi dari backend "
                             "(DNS/firewall/proxy, atau URL salah)."),
                })

            if model and models_listed and model not in models_listed:
                report["checks"].append({
                    "name": "Nama model", "ok": False, "status": None,
                    "error": f"`{model}` tidak ada di daftar model endpoint",
                    "detail": ", ".join(models_listed[:20]),
                    "hint": ("Pilih nama model persis dari daftar (tombol "
                             "**Muat model**) — nama yang salah dibalas 404/400 "
                             "oleh kebanyakan gateway."),
                })

            # ---- 2. POST non-streaming (bentuk curl di dokumentasi) --------
            payload = {"model": model, "messages": [{"role": "user",
                                                     "content": PROBE_MESSAGE}],
                       "max_tokens": PROBE_MAX_TOKENS, "temperature": 0.7}
            for stream in (False, True):
                label = ("POST chat/completions (non-streaming)" if not stream
                         else "POST chat/completions (streaming, dipakai app)")
                body = dict(payload, stream=stream)
                started = time.time()
                try:
                    if stream:
                        first = ""
                        status = 0
                        async with client.stream(
                            "POST", report["chat_url"], json=body,
                            headers=headers) as r:
                            status = r.status_code
                            if r.status_code == 200:
                                async for line in r.aiter_lines():
                                    if line.startswith("data:"):
                                        first = line
                                        break
                            else:
                                first = (await r.aread()).decode("utf-8", "replace")
                        latency = round((time.time() - started) * 1000)
                        if status == 200:
                            report["checks"].append({
                                "name": label, "ok": True, "status": 200,
                                "latency_ms": latency,
                                "detail": _excerpt(first, 200) or "(stream kosong)",
                            })
                        else:
                            report["checks"].append({
                                "name": label, "ok": False, "status": status,
                                "latency_ms": latency,
                                "error": _error_message(first) or _excerpt(first),
                                "hint": error_hint(status, first),
                            })
                    else:
                        r = await client.post(report["chat_url"], json=body,
                                              headers=headers)
                        latency = round((time.time() - started) * 1000)
                        if r.status_code == 200:
                            text = r.text
                            try:
                                data = r.json()
                                text = ((data.get("choices") or [{}])[0]
                                        .get("message", {}).get("content") or "")
                            except ValueError:
                                pass
                            report["checks"].append({
                                "name": label, "ok": True, "status": 200,
                                "latency_ms": latency,
                                "detail": _excerpt(text, 200) or "(jawaban kosong)",
                            })
                        else:
                            report["checks"].append({
                                "name": label, "ok": False,
                                "status": r.status_code, "latency_ms": latency,
                                "error": _error_message(r.text) or _excerpt(r.text),
                                "hint": error_hint(r.status_code, r.text),
                            })
                except httpx.HTTPError as exc:
                    report["checks"].append({
                        "name": label, "ok": False, "status": None,
                        "error": f"{type(exc).__name__}: {exc}",
                        "hint": "Koneksi putus saat request chat — cek timeout "
                                "proxy atau nama host.",
                    })
    except Exception as exc:  # noqa: BLE001 - diagnostics must never 500
        report["checks"].append({"name": "diagnostik", "ok": False,
                                 "status": None, "error": str(exc)})

    chat_checks = [c for c in report["checks"]
                   if c["name"].startswith("POST chat/completions")]
    model_check = next((c for c in report["checks"]
                        if c["name"] == "Nama model"), None)
    chat_ok = bool(chat_checks) and all(c["ok"] for c in chat_checks)
    # Nama model yang tidak terdaftar membuat hasil overall gagal: chat bisa saja
    # kebetulan dilayani model lain, tetapi itu bukan yang dikonfigurasi.
    report["ok"] = chat_ok and not (model_check and not model_check["ok"])

    if not report["ok"]:
        probe_check = next((c for c in report["checks"]
                            if c["name"].startswith("GET ") and not c["ok"]
                            and c.get("status") is None), None)
        failing = (probe_check                                  # endpoint mati
                   or next((c for c in chat_checks if not c["ok"]), None)
                   or model_check)
        if failing is not None:
            report["hint"] = failing.get("hint") or failing.get("error")
    return report
