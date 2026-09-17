"""generate_image tool — mode gambar.

Dua jalur, keduanya menghasilkan **artifact** yang terecord di registry:

  1. `openai`  — bila provider `openai` + API key tersedia, panggil endpoint
                 `/images/generations` (base64 response) dari gateway mana pun
                 yang kompatibel.
  2. `poster`  — fallback offline deterministik: poster SVG generatif dari hash
                 prompt (gradient, bentuk geometris, teks prompt). Selalu
                 berhasil tanpa jaringan, jadi mode gambar tetap layak demo
                 dan tetap jujur soal asal keluarannya (`generator` di meta).

Setiap hasil (termasuk fallback) ditandai generatornya — artefak tidak boleh
menyembunyikan asal-usulnya.
"""
from __future__ import annotations

import base64
import hashlib
import html
import json
import textwrap
from typing import Any

import httpx

from .base import Tool, ToolContext, ToolResult

#: Palet offline (gradien hangat/cool bergantian per hash prompt).
_PALETTES = [
    ("#4f46e5", "#9333ea", "#c026d3"),
    ("#0ea5e9", "#6366f1", "#8b5cf6"),
    ("#f59e0b", "#ef4444", "#ec4899"),
    ("#10b981", "#14b8a6", "#0ea5e9"),
    ("#f43f5e", "#f97316", "#eab308"),
]

MAX_PROMPT = 600


def _escape(t: str) -> str:
    return html.escape(t, quote=True)


def poster_svg(prompt: str) -> tuple[str, str]:
    """Poster SVG generatif dari prompt → (svg, palette_id)."""
    digest = hashlib.blake2b(prompt.encode("utf-8"), digest_size=16).digest()
    seed = int.from_bytes(digest, "big")
    c1, c2, c3 = _PALETTES[seed % len(_PALETTES)]
    ang = seed % 360
    # Bentuk geometris deterministik dari bit seed.
    shapes: list[str] = []
    for i in range(6):
        x = (seed >> (i * 5)) % 1024
        y = (seed >> (i * 7)) % 576
        r = 40 + (seed >> (i * 3)) % 160
        op = 0.08 + ((seed >> i) % 12) / 100
        if i % 2 == 0:
            shapes.append(
                f'<circle cx="{x}" cy="{y}" r="{r}" fill="url(#g2)" '
                f'opacity="{op:.2f}"/>')
        else:
            shapes.append(
                f'<rect x="{x - r // 2}" y="{y - r // 2}" width="{r}" '
                f'height="{r}" rx="{r // 5}" fill="#ffffff" opacity="{op:.2f}" '
                f'transform="rotate({ang % 90} {x} {y})"/>')

    wrapped = textwrap.wrap(prompt.strip() or "Gambar tanpa judul", width=30)[:6]
    lines = "".join(
        f'<tspan x="64" dy="{64 if i == 0 else 52}">{_escape(ln)}</tspan>'
        for i, ln in enumerate(wrapped)
    )
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="576" viewBox="0 0 1024 576" role="img" aria-label="{_escape(prompt[:120])}">
  <defs>
    <linearGradient id="g1" gradientTransform="rotate({ang})">
      <stop offset="0%" stop-color="{c1}"/><stop offset="55%" stop-color="{c2}"/><stop offset="100%" stop-color="{c3}"/>
    </linearGradient>
    <radialGradient id="g2"><stop offset="0%" stop-color="#ffffff"/><stop offset="100%" stop-color="#ffffff" stop-opacity="0"/></radialGradient>
  </defs>
  <rect width="1024" height="576" fill="url(#g1)"/>
  {''.join(shapes)}
  <text x="64" y="440" font-family="system-ui, -apple-system, 'Segoe UI', sans-serif" font-size="40" font-weight="700" fill="#ffffff">{lines}</text>
  <text x="64" y="528" font-family="system-ui, sans-serif" font-size="18" fill="#ffffff" opacity="0.75">Dibuat offline · Ask Anything · poster generatif dari prompt</text>
</svg>"""
    return svg, f"palette-{seed % len(_PALETTES) + 1}"


async def _via_openai(prompt: str, ctx: ToolContext) -> bytes | None:
    """Coba endpoint images dari gateway OpenAI-compatible; None bila tak bisa."""
    s = ctx.settings
    if s.provider != "openai" or not s.openai_api_key:
        return None
    base = s.openai_base_url.rstrip("/")
    url = base.removesuffix("/chat/completions") + "/images/generations"
    try:
        async with httpx.AsyncClient(timeout=120) as http:
            r = await http.post(
                url,
                headers={"Authorization": f"Bearer {s.openai_api_key}"},
                json={"model": "gpt-image-1", "prompt": prompt[:1000],
                      "n": 1, "size": "1024x1024"},
            )
            r.raise_for_status()
            payload = r.json()
        item = (payload.get("data") or [{}])[0]
        if item.get("b64_json"):
            return base64.b64decode(item["b64_json"])
        if item.get("url"):
            async with httpx.AsyncClient(timeout=120) as http:
                r2 = await http.get(item["url"])
                r2.raise_for_status()
                return r2.content
    except Exception:  # noqa: BLE001 - fallback offline, alasan ada di meta
        return None
    return None


async def run_generate_image(args: dict[str, Any], ctx: ToolContext) -> ToolResult:
    from .. import artifacts

    prompt = str(args.get("prompt", "")).strip()[:MAX_PROMPT]
    if not prompt:
        return ToolResult(summary="generate_image: prompt kosong",
                          data={"error": "prompt wajib diisi"}, ok=False)

    cid = getattr(ctx, "conversation_id", "") or ""
    rid = getattr(ctx, "run_id", "") or ""
    data = await _via_openai(prompt, ctx)
    if data is not None:
        generator, mime, ext = "openai-images", "image/png", "png"
        meta = {"generator": generator, "prompt": prompt}
        title = prompt[:70]
    else:
        svg, palette = poster_svg(prompt)
        data = svg.encode("utf-8")
        generator, mime, ext = "poster-v1 (offline)", "image/svg+xml", "svg"
        meta = {"generator": generator, "prompt": prompt, "palette": palette,
                "note": "Gateway gambar tidak tersedia — poster generatif "
                        "deterministik dari hash prompt."}
        title = prompt[:70]

    art = artifacts.register_artifact(
        settings=ctx.settings, kind="image", title=title,
        filename=f"image-{artifacts.db.now():.0f}.{ext}", mime=mime, data=data,
        conversation_id=cid, run_id=rid, meta=meta,
    )
    summary = f"Gambar dibuat ({generator}): {prompt[:60]}"
    return ToolResult(
        summary=summary,
        data={"artifact": {"id": art["id"], "url": art.get("url"),
                           "kind": "image", "title": art["title"],
                           "generator": generator},
              "prompt": prompt},
    )


GENERATE_IMAGE = Tool(
    name="generate_image",
    description=(
        "Generate a picture from a text prompt (mode gambar). Returns an "
        "artifact (image URL) the user can view/download. Offline gateway "
        "falls back to a deterministic generative poster."
    ),
    source="diagram",  # konten generatif — bukan bukti web, tidak disitasi
    parameters={
        "type": "object",
        "properties": {
            "prompt": {"type": "string",
                       "description": "Deskripsi gambar yang diinginkan user."},
        },
        "required": ["prompt"],
    },
    run=run_generate_image,
)
