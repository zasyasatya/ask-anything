"""The agent loop: provider streaming + tool execution + interpreter tracing.

Every observable step is emitted both to the SSE stream (frontend) and to the
SQLite trace store (mechanistic interpreter, replayable).

The trace is deliberately *mechanistic*: the interpreter exists to disclose the
blackbox, so each provider turn and each tool execution is recorded as
structured data — exact payload in, exact payload out, duration, status — not
as prose. Timings are relative to the run start (``t_ms``) so the UI can render
a log without doing arithmetic on wall clocks.
"""
from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import Any, Awaitable, Callable

import httpx

from .. import db
from ..config import Settings
from ..providers import BaseProvider
from ..sources import SourceRegistry, finalize_answer
from ..tools import ToolContext, get_tool, tool_schemas, tool_source
from .prompts import SYSTEM_PROMPT, TOOL_RESULT_HINT

EmitFn = Callable[[dict[str, Any]], Awaitable[None]]


def _history_to_llm(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert stored messages into OpenAI-protocol messages."""
    out: list[dict[str, Any]] = []
    for m in messages:
        role = m["role"]
        if role in ("user", "assistant"):
            out.append({"role": role, "content": m["content"]})
        elif role == "assistant_toolcalls":
            out.append(
                {
                    "role": "assistant",
                    "content": m["content"] or None,
                    "tool_calls": [
                        {
                            "id": tc["id"],
                            "type": "function",
                            "function": {
                                "name": tc["name"],
                                "arguments": json.dumps(
                                    tc["arguments"]),
                            },
                        }
                        for tc in m["meta"].get("tool_calls", [])
                    ],
                }
            )
        elif role == "tool":
            out.append(
                {
                    "role": "tool",
                    "tool_call_id": m["meta"].get("tool_call_id", ""),
                    "content": m["content"],
                }
            )
    return out


def _preview(text: str, limit: int = 160) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[:limit] + "…"


async def run_agent(
    *,
    conversation_id: str,
    user_message: str,
    history: list[dict[str, Any]],
    provider: BaseProvider,
    settings: Settings,
    emit: EmitFn,
) -> dict[str, Any]:
    """Run one agentic turn. Returns a summary dict (answer text, steps...)."""
    run_id = uuid.uuid4().hex[:8]
    seq = 0

    t0 = time.time()

    async def trace(type_: str, payload: dict[str, Any], stream: bool = True) -> None:
        nonlocal seq
        payload = {
            "t_ms": round((time.time() - t0) * 1000, 1),
            "step": steps,
            **payload,
        }
        db.add_trace(conversation_id, run_id, seq, type_, payload)
        seq += 1
        if stream:
            await emit({"type": type_, "run_id": run_id, "seq": seq - 1, **payload})

    steps = 0
    db.add_message(conversation_id, "user", user_message)

    await trace(
        "meta",
        {
            "provider": provider.name,
            "model": provider.model_label(),
            "temperature": settings.temperature,
            "max_tokens": settings.max_tokens,
            "max_steps": settings.max_steps,
            "logprobs": settings.logprobs,
            "top_logprobs": settings.top_logprobs,
            "thinking": settings.thinking if provider.name == "huggingface"
            else None,
            "tools": [t["function"]["name"] for t in tool_schemas()],
        },
    )

    llm_messages = _history_to_llm(history) + [
        {"role": "user", "content": user_message}
    ]
    sources = SourceRegistry()
    # Streamed as well as stored (the frontend keeps `prompt` out of the
    # timeline and shows it in the Prompt tab): a live run must disclose the
    # same thing a replayed conversation does.
    await trace(
        "prompt",
        {
            "system": SYSTEM_PROMPT,
            "messages": llm_messages,
            "tools": tool_schemas(),
            "message_count": len(llm_messages),
        },
    )

    tool_ctx = ToolContext(settings=settings)
    answer_parts: list[str] = []
    thinking_parts: list[str] = []
    usage: dict[str, Any] = {}
    final_events: list[dict[str, Any]] = []
    collected_calls: list[dict[str, Any]] | None = None
    diagram_titles: list[str] = []
    #: Artefak diagram dari tool create_diagram. Disimpan di meta pesan
    #: assistant supaya riwayat bisa merender kartu diagram yang sama seperti
    #: saat run berlangsung — tanpa bergantung pada model menyalin sumber
    #: Mermaid ke dalam teks jawabannya.
    diagrams: list[dict[str, Any]] = []

    async with httpx.AsyncClient() as http:
        tool_ctx.http = http
        for step in range(settings.max_steps):
            steps = step + 1
            collected_calls = None
            step_t0 = time.time()
            turn_answer: list[str] = []
            turn_thinking: list[str] = []

            await trace(
                "llm_request",
                {
                    "messages": llm_messages,
                    "message_count": len(llm_messages),
                    "tools": [t["function"]["name"] for t in tool_schemas()],
                    "sampling": {
                        "temperature": settings.temperature,
                        "max_tokens": settings.max_tokens,
                        "logprobs": settings.logprobs,
                        "top_logprobs": settings.top_logprobs,
                    },
                },
            )

            async for ev in provider.stream(
                llm_messages,
                tool_schemas(),
                temperature=settings.temperature,
                max_tokens=settings.max_tokens,
                logprobs=settings.logprobs,
                top_logprobs=settings.top_logprobs,
            ):
                if ev.type == "thinking":
                    thinking_parts.append(ev.data["text"])
                    turn_thinking.append(ev.data["text"])
                    await trace("thinking", {"text": ev.data["text"]})
                elif ev.type == "delta":
                    answer_parts.append(ev.data["text"])
                    turn_answer.append(ev.data["text"])
                    await trace("delta", {"text": ev.data["text"]})
                elif ev.type == "logprobs":
                    await trace("logprobs", ev.data)
                elif ev.type == "usage":
                    usage.update(ev.data)
                    await trace("usage", ev.data)
                elif ev.type == "tool_calls":
                    collected_calls = ev.data["calls"]
                elif ev.type == "error":
                    await trace("error", ev.data)
                    return {
                        "answer": "",
                        "error": ev.data.get("message"),
                        "steps": steps,
                    }
                elif ev.type == "done":
                    final_events.append(ev.data)
                elif ev.type == "note":
                    # Provider-level notice (e.g. payload downgrade for a
                    # gateway that lacks stream_options/logprobs).
                    await trace("note", ev.data)

            raw_answer = "".join(turn_answer)
            await trace(
                "llm_response",
                {
                    "text": raw_answer,
                    "text_preview": _preview(raw_answer),
                    "thinking": "".join(turn_thinking),
                    "finish_reason": (
                        final_events[-1].get("finish_reason")
                        if final_events else None
                    ),
                    "tool_calls": [
                        {"id": c["id"], "name": c["name"],
                         "arguments": c["arguments"]}
                        for c in (collected_calls or [])
                    ],
                    "chars": len(raw_answer),
                    "duration_ms": round((time.time() - step_t0) * 1000, 1),
                },
            )

            if not collected_calls:
                break  # model produced a final answer

            # ---- execute tools ----
            llm_messages.append(
                {
                    "role": "assistant",
                    "content": raw_answer or None,
                    "tool_calls": [
                        {
                            "id": c["id"],
                            "type": "function",
                            "function": {
                                "name": c["name"],
                                "arguments": json.dumps(
                                    c["arguments"]),
                            },
                        }
                        for c in collected_calls
                    ],
                }
            )
            db.add_message(
                conversation_id,
                "assistant_toolcalls",
                raw_answer,
                meta={"tool_calls": collected_calls},
            )
            answer_parts = []

            tasks = []
            for call in collected_calls:
                await trace(
                    "tool_call",
                    {
                        "id": call["id"],
                        "name": call["name"],
                        "arguments": call["arguments"],
                        "source": tool_source(call["name"]),
                        "args_preview": _preview(
                            json.dumps(call["arguments"], ensure_ascii=False)),
                    },
                )
                tool = get_tool(call["name"])
                if tool is None:
                    await trace(
                        "tool_result",
                        {"id": call["id"], "name": call["name"],
                         "source": "compute",
                         "summary": f"tool tidak dikenal: {call['name']}",
                         "ok": False, "hits": None, "error": "unknown tool",
                         "duration_ms": 0.0,
                         "data": {"error": "unknown tool"}},
                    )
                    llm_messages.append(
                        {"role": "tool", "tool_call_id": call["id"],
                         "content": "Error: unknown tool"}
                    )
                    continue
                tasks.append((call, tool))

            for call, tool in tasks:
                run_t0 = time.time()
                error: str | None = None
                try:
                    result = await asyncio.wait_for(
                        tool.run(call["arguments"], tool_ctx), timeout=30
                    )
                    payload = result.data
                    summary = result.summary
                    ok = result.ok
                    hits = result.hits
                except Exception as exc:  # noqa: BLE001 - report to the model
                    result = None
                    payload = {"error": str(exc)}
                    summary = f"{type(exc).__name__}: {exc}"
                    ok = False
                    hits = None
                    error = summary
                duration_ms = round((time.time() - run_t0) * 1000, 1)

                # Browser payloads become citable sources; diagram payloads do
                # not (generated content must never pose as external evidence).
                added = 0
                if tool.evidence:
                    added = sources.register_tool_result(
                        tool.name, call["arguments"], payload)

                data = _cap(payload)
                await trace(
                    "tool_result",
                    {
                        "id": call["id"],
                        "name": tool.name,
                        "source": tool.source,
                        "label": tool.label,
                        "summary": summary,
                        "ok": ok,
                        "hits": hits,
                        "new_sources": added,
                        "error": error,
                        "duration_ms": duration_ms,
                        "data": data,
                    },
                )
                if tool.evidence and hits == 0:
                    await trace(
                        "note",
                        {"message": f"Browser: 0 hasil dari {tool.name} — tidak "
                                    "ada bukti web untuk langkah ini.",
                         "status": "no-results", "tool": tool.name},
                    )
                if tool.name == "create_diagram" and isinstance(
                        payload, dict) and payload.get("mermaid"):
                    title = str(payload.get("title") or "Diagram")
                    diagram_titles.append(title)
                    diagrams.append({
                        "tool": tool.name,
                        "source": payload.get("source") or "structured",
                        "kind": payload.get("kind") or "flowchart",
                        "title": title,
                        "mermaid": str(payload["mermaid"]),
                        "warnings": payload.get("warnings") or [],
                    })

                content = json.dumps(data, default=str)
                db.add_message(
                    conversation_id, "tool", content,
                    meta={"tool_call_id": call["id"], "name": tool.name,
                          "source": tool.source, "ok": ok,
                          # outcome disimpan agar riwayat menampilkan status yang
                          # sama dengan saat run berlangsung (bukan sekadar ✓)
                          "hits": hits, "summary": summary,
                          "error": error, "new_sources": added,
                          "duration_ms": duration_ms},
                )
                llm_messages.append(
                    {"role": "tool", "tool_call_id": call["id"], "content": content}
                )

            llm_messages.append({"role": "system", "content": TOOL_RESULT_HINT})
            # The model only ever cites what it can see: hand it the numbered
            # source list right after the raw tool payloads.
            llm_messages.append(
                {"role": "system", "content": sources.prompt_block()}
            )
            await trace(
                "sources",
                {
                    "total": len(sources.items),
                    "items": sources.to_dicts(),
                    "block": sources.as_marked_list(),
                },
            )

    answer = "".join(answer_parts).strip()

    # The loop can end because `max_steps` ran out while the model was still
    # asking for tools: without a fallback the UI would render an empty bubble
    # and the trace would claim success. Be explicit instead.
    stopped_reason = "stop"
    if not answer and collected_calls:
        stopped_reason = "max_steps"
        answer = (
            f"Model memakai seluruh {settings.max_steps} langkah untuk memanggil "
            f"tool ({', '.join(sorted({c['name'] for c in collected_calls}))}) "
            "tanpa menghasilkan jawaban final. Coba sederhanakan pertanyaan, "
            "naikkan `ASK_MAX_STEPS`, atau pakai model yang lebih besar — "
            "semua langkahnya ada di tab Timeline."
        )
        await trace("note", {"message": answer, "status": "max_steps"})

    # ---- citations: every web claim must be traceable to a numbered source --
    answer, citations = finalize_answer(answer, sources)
    await trace(
        "citations",
        {
            "status": citations["status"],
            "total": citations["total"],
            "cited": citations["cited"],
            "uncited": citations["uncited"],
            "invalid": citations["invalid"],
            "detail": citations["detail"],
            "sources": sources.to_dicts(),
        },
    )

    elapsed = round((time.time() - t0) * 1000, 1)
    usage["latency_ms"] = elapsed
    usage["steps"] = steps
    await trace("done", {"answer": answer, "stopped_reason": stopped_reason,
                         **usage})

    db.add_message(
        conversation_id,
        "assistant",
        answer,
        meta={
            "thinking": "".join(thinking_parts),
            "usage": usage,
            "stopped_reason": stopped_reason,
            "sources": sources.to_dicts(),
            "citations": citations,
            # Provenance of the visuals in this answer: diagrams rendered from
            # a create_diagram payload are tool output, not free-form model
            # text — the UI labels them accordingly.
            "diagram_origin": (
                {"tool": "create_diagram", "titles": diagram_titles}
                if diagram_titles else None
            ),
            #: Payload diagram siap render (kartu diagram di UI). Ini yang
            #: membuat diagram tetap ada walau model tidak menulis fence
            #: ```mermaid di jawabannya.
            "diagrams": diagrams,
        },
    )
    return {"answer": answer, "steps": steps, "usage": usage,
            "run_id": run_id, "citations": citations,
            "sources": sources.to_dicts(), "diagrams": diagrams,
            "error": None}


def _cap(data: dict[str, Any], limit: int = 12000) -> dict[str, Any]:
    """Truncate long strings in tool payloads before storing/streaming."""
    out = {}
    for k, v in data.items():
        if isinstance(v, str) and len(v) > limit:
            out[k] = v[:limit] + " …[truncated]"
        elif isinstance(v, list) and k == "results":
            out[k] = v[:8]
        else:
            out[k] = v
    return out
