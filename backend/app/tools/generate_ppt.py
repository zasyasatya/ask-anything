"""generate_ppt tool — mode PPT: kerangka → deck .pptx (artifact).

Paket: `python-pptx` (requirements.txt). Bila belum ter-install, tool gagal
dengan pesan install yang jelas — bukan deck kosong. Struktur deck dibangun
dari outline terstruktur yang keluarkan model (judul + bullet per slide),
sehingga hasilnya deterministik dan bisa di-audit di interpreter.
"""
from __future__ import annotations

import io
from typing import Any

from .base import Tool, ToolContext, ToolResult

MAX_SLIDES = 30
MAX_BULLETS = 12
MAX_TITLE = 160
MAX_BULLET = 240


def _clean(v: Any, limit: int) -> str:
    return " ".join(str(v or "").split())[:limit]


def build_pptx(title: str, slides: list[dict[str, Any]]) -> bytes:
    """Rakit deck dari outline. Raises ImportError bila python-pptx absen."""
    try:
        from pptx import Presentation
        from pptx.util import Inches, Pt
    except ImportError as exc:  # pragma: no cover - env tanpa python-pptx
        raise RuntimeError(
            "python-pptx belum ter-install — jalankan: "
            "pip install -r backend/requirements.txt"
        ) from exc

    prs = Presentation()
    # Slide judul
    s = prs.slides.add_slide(prs.slide_layouts[0])
    s.shapes.title.text = title or "Presentasi"
    if len(s.placeholders) > 1:
        s.placeholders[1].text = "Dibuat oleh Ask Anything — mode PPT"

    for sl in slides:
        slide = prs.slides.add_slide(prs.slide_layouts[1])
        slide.shapes.title.text = _clean(sl.get("title"), MAX_TITLE) or "-"
        body = slide.placeholders[1].text_frame
        body.word_wrap = True
        bullets = sl.get("bullets") or []
        for i, b in enumerate(bullets[:MAX_BULLETS]):
            p = body.paragraphs[0] if i == 0 else body.add_paragraph()
            p.text = _clean(b, MAX_BULLET)
            p.font.size = Pt(18)

    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()


def _validate(args: dict[str, Any]) -> tuple[str, list[dict[str, Any]]] | str:
    title = _clean(args.get("title"), MAX_TITLE) or "Presentasi"
    raw = args.get("slides")
    if not isinstance(raw, list) or not raw:
        return "slides wajib berupa list berisi {title, bullets[]}"
    slides: list[dict[str, Any]] = []
    for sl in raw[:MAX_SLIDES]:
        if not isinstance(sl, dict):
            continue
        bullets = sl.get("bullets")
        if isinstance(bullets, str):
            bullets = [bullets]
        if not isinstance(bullets, list):
            bullets = []
        slides.append({"title": _clean(sl.get("title"), MAX_TITLE),
                       "bullets": [_clean(b, MAX_BULLET) for b in bullets
                                   if _clean(b, MAX_BULLET)]})
    if not slides:
        return "tidak ada slide valid di outline"
    return title, slides


async def run_generate_ppt(args: dict[str, Any], ctx: ToolContext) -> ToolResult:
    from .. import artifacts

    parsed = _validate(args)
    if isinstance(parsed, str):
        return ToolResult(summary=f"generate_ppt: {parsed}",
                          data={"error": parsed}, ok=False)
    title, slides = parsed
    try:
        data = build_pptx(title, slides)
    except RuntimeError as exc:
        return ToolResult(summary=f"generate_ppt error: {exc}",
                          data={"error": str(exc)}, ok=False)

    safe_title = "".join(c if c.isalnum() or c in "-_ " else ""
                         for c in title).strip() or "deck"
    art = artifacts.register_artifact(
        settings=ctx.settings, kind="pptx", title=title,
        filename=f"{safe_title[:40]}.pptx",
        mime="application/vnd.openxmlformats-officedocument.presentationml."
             "presentation",
        data=data,
        conversation_id=getattr(ctx, "conversation_id", "") or "",
        run_id=getattr(ctx, "run_id", "") or "",
        meta={"slide_count": len(slides),
              "outline": [{"title": s["title"], "bullets": s["bullets"]}
                          for s in slides]},
    )
    return ToolResult(
        summary=f"Deck PPT dibuat: {title} ({len(slides)} slide)",
        data={"artifact": {"id": art["id"], "url": art.get("url"),
                           "kind": "pptx", "title": art["title"],
                           "slide_count": len(slides)},
              "outline": [{"title": s["title"], "bullets": s["bullets"]}
                          for s in slides]},
    )


GENERATE_PPT = Tool(
    name="generate_ppt",
    description=(
        "Create a PowerPoint deck (.pptx) from a structured outline (mode "
        "PPT). Provide a deck title and 3-10 slides, each {title, bullets[]}. "
        "Returns an artifact the user can download."
    ),
    source="diagram",
    parameters={
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Judul deck"},
            "slides": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "bullets": {"type": "array",
                                    "items": {"type": "string"}},
                    },
                    "required": ["title", "bullets"],
                },
            },
        },
        "required": ["title", "slides"],
    },
    run=run_generate_ppt,
)
