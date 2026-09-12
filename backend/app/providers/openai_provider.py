"""OpenAI-protocol streaming client (used for OpenAI API *and* local HF servers).

Local HuggingFace serving (llama.cpp `llama-server`, vLLM, LM Studio, TGI…) all
expose this exact protocol, so one robust client covers both worlds. It also
extracts streaming logprobs and <think> blocks for the mechanistic interpreter.
"""
from __future__ import annotations

import json
from typing import Any, AsyncIterator

import httpx

from .base import BaseProvider, StreamEvent, ToolCall

THINK_OPEN = "<think>"
THINK_CLOSE = "</think>"


class _ThinkParser:
    """Splits a content stream into (kind, chunk) pairs, handling <think> tags
    that may be split across chunk boundaries."""

    def __init__(self) -> None:
        self.mode = "answer"
        self.hold = ""

    def feed(self, text: str) -> list[tuple[str, str]]:
        self.hold += text
        out: list[tuple[str, str]] = []
        while True:
            if self.mode == "answer":
                i = self.hold.find(THINK_OPEN)
                if i >= 0:
                    if i > 0:
                        out.append(("answer", self.hold[:i]))
                    self.hold = self.hold[i + len(THINK_OPEN):]
                    self.mode = "thinking"
                    continue
                cut = self._safe_cut(self.hold, THINK_OPEN)
                if cut > 0:
                    out.append(("answer", self.hold[:cut]))
                    self.hold = self.hold[cut:]
                break
            else:
                i = self.hold.find(THINK_CLOSE)
                if i >= 0:
                    if i > 0:
                        out.append(("thinking", self.hold[:i]))
                    self.hold = self.hold[i + len(THINK_CLOSE):]
                    self.mode = "answer"
                    continue
                cut = self._safe_cut(self.hold, THINK_CLOSE)
                if cut > 0:
                    out.append(("thinking", self.hold[:cut]))
                    self.hold = self.hold[cut:]
                break
        return out

    def flush(self) -> list[tuple[str, str]]:
        if self.hold:
            out = [(self.mode, self.hold)]
            self.hold = ""
            return out
        return []

    @staticmethod
    def _safe_cut(s: str, tag: str) -> int:
        keep = 0
        for length in range(1, len(tag)):
            if s.endswith(tag[:length]):
                keep = max(keep, length)
        return len(s) - keep


class OpenAIProtocolProvider(BaseProvider):
    """Streams chat completions from any OpenAI-compatible endpoint."""

    name = "openai"

    def __init__(self, base_url: str, api_key: str = "", model: str = "",
                 transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.transport = transport

    def model_label(self) -> str:
        return self.model or "openai"

    def _headers(self) -> dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    async def stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        logprobs: bool = False,
        top_logprobs: int = 4,
    ) -> AsyncIterator[StreamEvent]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if tools:
            payload["tools"] = tools
        if logprobs:
            payload["logprobs"] = True
            payload["top_logprobs"] = top_logprobs

        url = f"{self.base_url}/chat/completions"
        parser = _ThinkParser()
        tool_acc: dict[int, dict[str, Any]] = {}
        finish_reason: str | None = None

        timeout = httpx.Timeout(connect=15.0, read=None, write=30.0, pool=15.0)
        try:
            async with httpx.AsyncClient(timeout=timeout,
                                         transport=self.transport) as client:
                async with client.stream(
                    "POST", url, json=payload, headers=self._headers()
                ) as resp:
                    if resp.status_code != 200:
                        body = (await resp.aread()).decode("utf-8", "replace")
                        yield StreamEvent(
                            "error",
                            {"message": f"HTTP {resp.status_code}: {body[:600]}",
                             "status": resp.status_code},
                        )
                        return
                    async for line in resp.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if not data or data == "[DONE]":
                            continue
                        try:
                            obj = json.loads(data)
                        except json.JSONDecodeError:
                            continue

                        usage = obj.get("usage")
                        if usage:
                            yield StreamEvent(
                                "usage",
                                {
                                    "prompt_tokens": usage.get("prompt_tokens"),
                                    "completion_tokens": usage.get(
                                        "completion_tokens"),
                                    "total_tokens": usage.get("total_tokens"),
                                },
                            )
                        choices = obj.get("choices") or []
                        if not choices:
                            continue
                        choice = choices[0]
                        delta = choice.get("delta") or {}

                        reasoning = delta.get("reasoning_content")
                        if reasoning:
                            yield StreamEvent("thinking", {"text": reasoning})

                        content = delta.get("content")
                        if content:
                            for kind, chunk in parser.feed(content):
                                if kind == "thinking":
                                    yield StreamEvent("thinking", {"text": chunk})
                                else:
                                    yield StreamEvent("delta", {"text": chunk})

                        lp = choice.get("logprobs")
                        if lp and lp.get("content"):
                            items = []
                            for tok in lp["content"]:
                                items.append(
                                    {
                                        "token": tok.get("token"),
                                        "logprob": tok.get("logprob"),
                                        "top": [
                                            {"token": t.get("token"),
                                             "logprob": t.get("logprob")}
                                            for t in tok.get("top_logprobs") or []
                                        ],
                                    }
                                )
                            yield StreamEvent("logprobs", {"items": items})

                        tcs = delta.get("tool_calls")
                        if tcs:
                            for tc in tcs:
                                idx = tc.get("index", 0)
                                slot = tool_acc.setdefault(
                                    idx, {"id": "", "name": "", "arguments": ""}
                                )
                                if tc.get("id"):
                                    slot["id"] = tc["id"]
                                fn = tc.get("function") or {}
                                if fn.get("name"):
                                    slot["name"] += fn["name"]
                                if fn.get("arguments"):
                                    slot["arguments"] += fn["arguments"]

                        fr = choice.get("finish_reason")
                        if fr:
                            finish_reason = fr
        except httpx.HTTPError as exc:
            yield StreamEvent("error", {"message": f"connection error: {exc}"})
            return

        for kind, chunk in parser.flush():
            if kind == "thinking":
                yield StreamEvent("thinking", {"text": chunk})
            else:
                yield StreamEvent("delta", {"text": chunk})

        if tool_acc:
            calls = []
            for idx in sorted(tool_acc):
                slot = tool_acc[idx]
                try:
                    args = json.loads(slot["arguments"] or "{}")
                except json.JSONDecodeError:
                    args = {"_raw": slot["arguments"]}
                calls.append(
                    ToolCall(id=slot["id"] or f"call_{idx}", name=slot["name"],
                             arguments=args)
                )
            yield StreamEvent("tool_calls", {"calls": [c.to_dict() for c in calls]})

        yield StreamEvent("done", {"finish_reason": finish_reason or "stop"})
