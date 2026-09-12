"""The agent loop: provider streaming + tool execution + interpreter tracing.

Every observable step is emitted both to the SSE stream (frontend) and to the
SQLite trace store (mechanistic interpreter, replayable).
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
from ..providers import BaseProvider, StreamEvent
from ..tools import ToolContext, get_tool, tool_schemas
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

    async def trace(type_: str, payload: dict[str, Any], stream: bool = True) -> None:
        nonlocal seq
        db.add_trace(conversation_id, run_id, seq, type_, payload)
        seq += 1
        if stream:
            await emit({"type": type_, "run_id": run_id, **payload})

    t0 = time.time()
    db.add_message(conversation_id, "user", user_message)

    await trace(
        "meta",
        {
            "provider": provider.name,
            "model": provider.model_label(),
            "temperature": settings.temperature,
            "max_steps": settings.max_steps,
            "logprobs": settings.logprobs,
        },
    )

    llm_messages = _history_to_llm(history) + [
        {"role": "user", "content": user_message}
    ]
    await trace(
        "prompt",
        {
            "system": SYSTEM_PROMPT,
            "messages": llm_messages,
            "tools": [t["function"]["name"] for t in tool_schemas()],
        },
        stream=False,  # prompt assembly shown in the Prompt tab, not timeline
    )

    tool_ctx = ToolContext(settings=settings)
    answer_parts: list[str] = []
    thinking_parts: list[str] = []
    usage: dict[str, Any] = {}
    steps = 0
    final_events: list[dict[str, Any]] = []

    async with httpx.AsyncClient() as http:
        tool_ctx.http = http
        for step in range(settings.max_steps):
            steps = step + 1
            collected_calls: list[dict[str, Any]] | None = None

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
                    await trace("thinking", {"text": ev.data["text"]})
                elif ev.type == "delta":
                    answer_parts.append(ev.data["text"])
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

            if not collected_calls:
                break  # model produced a final answer

            # ---- execute tools ----
            llm_messages.append(
                {
                    "role": "assistant",
                    "content": "".join(answer_parts) or None,
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
                "".join(answer_parts),
                meta={"tool_calls": collected_calls},
            )
            answer_parts = []

            tasks = []
            for call in collected_calls:
                await trace("tool_call", call)
                tool = get_tool(call["name"])
                if tool is None:
                    await trace(
                        "tool_result",
                        {"id": call["id"], "name": call["name"],
                         "summary": f"tool tidak dikenal: {call['name']}",
                         "data": {"error": "unknown tool"}},
                    )
                    llm_messages.append(
                        {"role": "tool", "tool_call_id": call["id"],
                         "content": "Error: unknown tool"}
                    )
                    continue
                tasks.append((call, tool))

            for call, tool in tasks:
                try:
                    result = await asyncio.wait_for(
                        tool.run(call["arguments"], tool_ctx), timeout=30
                    )
                    payload = result.data
                except Exception as exc:  # noqa: BLE001 - report to the model
                    result = None
                    payload = {"error": str(exc)}
                summary = result.summary if result else f"error: {payload}"
                await trace(
                    "tool_result",
                    {"id": call["id"], "name": tool.name, "summary": summary,
                     "data": _cap(payload)},
                )
                content = json.dumps(_cap(payload), default=str)
                db.add_message(
                    conversation_id, "tool", content,
                    meta={"tool_call_id": call["id"], "name": tool.name},
                )
                llm_messages.append(
                    {"role": "tool", "tool_call_id": call["id"], "content": content}
                )

            llm_messages.append({"role": "system", "content": TOOL_RESULT_HINT})

    answer = "".join(answer_parts).strip()
    elapsed = round((time.time() - t0) * 1000, 1)
    usage["latency_ms"] = elapsed
    usage["steps"] = steps
    await trace("done", {"answer": answer, **usage})

    db.add_message(
        conversation_id,
        "assistant",
        answer,
        meta={"thinking": "".join(thinking_parts), "usage": usage},
    )
    return {"answer": answer, "steps": steps, "usage": usage,
            "run_id": run_id, "error": None}


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
