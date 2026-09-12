"""Emulates a local HuggingFace server (llama.cpp `llama-server` OpenAI API).

Used for:
  * integration tests of the huggingface provider over real HTTP/SSE,
  * a zero-GPU demo mode (`run.py --demo`) so the whole platform runs even on
    machines without a downloaded GGUF.

It behaves like a small agentic Qwen3-style model: emits <think> blocks,
calls tools (web_search / create_diagram), streams logprobs, and finishes with
usage — exactly the wire format llama.cpp produces.
"""
from __future__ import annotations

import json
import re
import time

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse

app = FastAPI(title="fake-llama-server")

MODEL = "Qwen/Qwen3-8B-GGUF"
_SEARCH_RE = re.compile(r"\b(cari|search|berita|news|harga|price|cuaca|weather)\b", re.I)
_DIAGRAM_RE = re.compile(r"\b(diagram|flowchart|alur|graph|graf|mindmap|skema)\b", re.I)


def _chunk(delta: dict, finish=None, logprobs=None, usage=None, model=MODEL):
    obj = {
        "id": "chatcmpl-fake",
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {"index": 0, "delta": delta,
             "logprobs": logprobs, "finish_reason": finish}
        ],
    }
    if usage is not None:
        obj["usage"] = usage
        obj["choices"] = []
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


def _lp(token: str):
    return {"content": [
        {"token": token, "logprob": -0.12,
         "top_logprobs": [
             {"token": token, "logprob": -0.12},
             {"token": "model", "logprob": -2.4},
             {"token": "agent", "logprob": -3.1},
         ]}
    ]}


def _decide(messages):
    last_user = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            last_user = m.get("content") or ""
            break
    has_tool = any(m.get("role") == "tool" for m in messages)
    tool_mermaid = None
    for m in messages:
        if m.get("role") == "tool" and "mermaid" in (m.get("content") or ""):
            try:
                tool_mermaid = json.loads(m["content"]).get("mermaid")
            except Exception:
                tool_mermaid = None
    return last_user, has_tool, tool_mermaid


async def _generate(messages, want_logprobs: bool):
    last_user, has_tool, tool_mermaid = _decide(messages)
    yield _chunk({"role": "assistant", "content": ""})

    if _SEARCH_RE.search(last_user) and not has_tool:
        think = ("The user asks for current information; my weights are frozen, "
                 "so I must call web_search before answering.")
        yield _chunk({"content": "<think>"})
        for w in think.split(" "):
            yield _chunk({"content": " " + w})
        yield _chunk({"content": "</think>"})
        args = json.dumps({"query": last_user[:80]})
        yield _chunk({"tool_calls": [
            {"index": 0, "id": "call_fake_1", "type": "function",
             "function": {"name": "web_search", "arguments": ""}}]})
        # stream arguments in pieces like llama.cpp does
        for i in range(0, len(args), 12):
            yield _chunk({"tool_calls": [
                {"index": 0, "id": "", "type": "function",
                 "function": {"name": "", "arguments": args[i:i + 12]}}]})
        yield _chunk({}, finish="tool_calls")
        yield _chunk({}, usage={"prompt_tokens": 140, "completion_tokens": 42,
                                "total_tokens": 182})
        yield "data: [DONE]\n\n"
        return

    if _DIAGRAM_RE.search(last_user) and not has_tool and tool_mermaid is None:
        think = "A visual is requested: build nodes/edges via create_diagram."
        yield _chunk({"content": "<think>"})
        for w in think.split(" "):
            yield _chunk({"content": " " + w})
        yield _chunk({"content": "</think>"})
        args = json.dumps({
            "kind": "flowchart",
            "title": "Alur Agent Ask-Anything",
            "nodes": [
                {"id": "q", "label": "Pertanyaan user"},
                {"id": "r", "label": "Reasoning / planning"},
                {"id": "w", "label": "web_search (bila perlu)"},
                {"id": "d", "label": "create_diagram"},
                {"id": "a", "label": "Jawaban + diagram"},
            ],
            "edges": [
                {"from": "q", "to": "r"},
                {"from": "r", "to": "w", "label": "butuh fakta"},
                {"from": "w", "to": "d"},
                {"from": "r", "to": "d", "label": "langsung"},
                {"from": "d", "to": "a"},
            ],
        })
        yield _chunk({"tool_calls": [
            {"index": 0, "id": "call_fake_2", "type": "function",
             "function": {"name": "create_diagram", "arguments": ""}}]})
        for i in range(0, len(args), 24):
            yield _chunk({"tool_calls": [
                {"index": 0, "id": "", "type": "function",
                 "function": {"name": "", "arguments": args[i:i + 24]}}]})
        yield _chunk({}, finish="tool_calls")
        yield _chunk({}, usage={"prompt_tokens": 150, "completion_tokens": 88,
                                "total_tokens": 238})
        yield "data: [DONE]\n\n"
        return

    # ---- final answer turn ----
    think = "All tool results are in. I will compose the final answer now."
    yield _chunk({"content": "<think>"})
    for w in think.split(" "):
        yield _chunk({"content": " " + w})
    yield _chunk({"content": "</think>"})

    parts = ["Baik, berikut jawaban saya berdasarkan proses agent: "]
    if tool_mermaid:
        parts.append("diagram sudah saya bangun lewat tool `create_diagram`:\n\n"
                     "```mermaid\n" + tool_mermaid + "\n```\n\n")
    if any(m.get("role") == "tool" and "results" in (m.get("content") or "")
           for m in messages):
        try:
            data = json.loads([m for m in messages if m.get("role") == "tool"][0]
                              ["content"])
            for r in data.get("results", [])[:3]:
                parts.append(f"- [{r.get('title')}]({r.get('url')}) — "
                             f"{r.get('snippet', '')[:120]}\n")
        except Exception:
            pass
    parts.append("\nSemua langkah (thinking, tool call, logprobs) terlihat di "
                 "panel Mechanistic Interpreter.")

    text = "".join(parts)
    tokens = re.findall(r"\S+\s*", text)
    for i, tok in enumerate(tokens):
        yield _chunk({"content": tok},
                     logprobs=_lp(tok.strip()[:8]) if want_logprobs else None)
    yield _chunk({}, finish="stop")
    yield _chunk({}, usage={"prompt_tokens": 210, "completion_tokens": len(tokens),
                            "total_tokens": 210 + len(tokens)})
    yield "data: [DONE]\n\n"


@app.post("/v1/chat/completions")
async def completions(request: Request):
    body = await request.json()
    want_logprobs = bool(body.get("logprobs"))
    return StreamingResponse(
        _generate(body.get("messages", []), want_logprobs),
        media_type="text/event-stream",
    )


@app.get("/v1/models")
async def models():
    return {"data": [{"id": MODEL, "object": "model"}]}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8081)
