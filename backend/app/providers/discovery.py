"""Discover the models an OpenAI-compatible endpoint actually serves.

Every provider mode (local llama.cpp server, OpenAI, third-party gateway) exposes
`GET <base>/models`, but the response shape is *not* standardised:

    OpenAI / vLLM / TGI      {"object":"list","data":[{"id":"gpt-4o-mini", ...}]}
    llama.cpp (>= b4xxx)     {"object":"list","data":[{"id":"/models/x.gguf"}],
                              "models":[{"model":"/models/x.gguf", ...}]}   ← both!
    llama.cpp (lama-lama)    {"models":[{"model":"..."}]}
    some gateways            ["model-a", "model-b"]

The UI needs one list it can put in a dropdown, so we normalise all of them here
and never raise: a network/auth failure is data the UI shows next to the field
(`{"ok": false, "error": ...}`), not an exception.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx

from .url_utils import models_url

TIMEOUT = 10.0


def _label(model_id: str) -> str:
    """Human label for a model id (llama.cpp reports full GGUF paths)."""
    if "/" in model_id:
        stem = Path(model_id).stem
        if stem:
            return stem
    return model_id


def _collect(payload: Any) -> list[str]:
    """Extract model ids from any of the shapes documented in the module doc."""
    ids: list[str] = []

    def push(value: Any) -> None:
        if isinstance(value, str) and value.strip():
            ids.append(value.strip())
        elif isinstance(value, dict):
            for key in ("id", "model", "name"):
                if isinstance(value.get(key), str) and value[key].strip():
                    ids.append(value[key].strip())
                    return

    if isinstance(payload, dict):
        for item in payload.get("data") or []:
            push(item)
        if not ids:
            for item in payload.get("models") or []:
                push(item)
    elif isinstance(payload, list):
        for item in payload:
            push(item)

    # de-duplicate, keep order (llama.cpp sends each model twice)
    seen: set[str] = set()
    return [m for m in ids if not (m in seen or seen.add(m))]


async def list_remote_models(
    base_url: str,
    api_key: str = "",
    transport: httpx.AsyncBaseTransport | None = None,
    timeout: float = TIMEOUT,
) -> dict[str, Any]:
    """Probe `<base>/models`. Returns a UI-ready dict; never raises."""
    url = models_url(base_url) if base_url else ""
    if not url:
        return {"ok": False, "url": "", "status": None, "models": [],
                "error": "base URL kosong — isi dulu endpoint-nya"}

    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    try:
        async with httpx.AsyncClient(timeout=timeout, transport=transport) as client:
            resp = await client.get(url, headers=headers)
    except httpx.HTTPError as exc:
        return {"ok": False, "url": url, "status": None, "models": [],
                "error": f"tidak bisa dihubungi: {exc.__class__.__name__}: {exc}"}

    if resp.status_code != 200:
        hint = {401: "API key ditolak (401)", 403: "API key tidak berhak (403)",
                404: "endpoint /models tidak ada (404)"}.get(resp.status_code)
        body = resp.text[:200]
        return {"ok": False, "url": url, "status": resp.status_code, "models": [],
                "error": hint or f"HTTP {resp.status_code}", "detail": body}

    try:
        payload = resp.json()
    except ValueError:
        return {"ok": False, "url": url, "status": resp.status_code, "models": [],
                "error": "jawaban /models bukan JSON"}

    ids = _collect(payload)
    if not ids:
        return {"ok": False, "url": url, "status": resp.status_code, "models": [],
                "error": "endpoint menjawab 200 tetapi tidak berisi daftar model",
                "detail": str(payload)[:200]}

    return {"ok": True, "url": url, "status": resp.status_code,
            "models": [{"id": m, "label": _label(m)} for m in ids],
            "error": None}
