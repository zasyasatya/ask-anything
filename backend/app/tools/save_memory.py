"""save_memory tool — agent mencatat fakta/pedoman jangka panjang.

Diatur admin (`memory.allow_ai_write`): kalau dimatikan, tool tetap terdaftar
ke model bila mode memori aktif tapi eksekusinya ditolak policy di agent loop
— dan penolakan itu terecord di interpreter.
"""
from __future__ import annotations

from typing import Any

from .base import Tool, ToolContext, ToolResult

MAX_CONTENT = 500


async def run_save_memory(args: dict[str, Any], ctx: ToolContext) -> ToolResult:
    from .. import memory

    content = str(args.get("content", "")).strip()[:MAX_CONTENT]
    key = str(args.get("key", "")).strip()[:80]
    if not content:
        return ToolResult(summary="save_memory: konten kosong",
                          data={"error": "content wajib diisi"}, ok=False)
    mem = memory.add_memory(scope="global", content=content, key=key,
                            source="ai", enabled=True)
    return ToolResult(
        summary=f"Memori tersimpan: {content[:60]}",
        data={"memory": memory.meta_of(mem)},
    )


SAVE_MEMORY = Tool(
    name="save_memory",
    description=(
        "Save a durable memory/ground rule for future conversations (only for "
        "stable user preferences or project facts, not chit-chat)."
    ),
    source="compute",
    parameters={
        "type": "object",
        "properties": {
            "content": {"type": "string",
                        "description": "Fakta/pedoman yang perlu diingat."},
            "key": {"type": "string",
                    "description": "Label pendek opsional, mis. 'preferensi'."},
        },
        "required": ["content"],
    },
    run=run_save_memory,
)
