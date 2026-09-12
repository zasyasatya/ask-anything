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
from .url_utils import chat_completions_url, normalize_openai_base_url

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
    """Streams chat completions from any OpenAI-compatible endpoint.

    `base_url` may be given in any of the shapes people copy from API docs
    (bare host, `…/v1`, `…/v1/`, or the full `…/v1/chat/completions`); it is
    canonicalised by :mod:`.url_utils` before the endpoint path is appended.
    """

    name = "openai"

    # HTTP statuses that mean "this payload shape is not accepted here" rather
    # than "the server is broken". llama.cpp answers **500** with
    # `logprobs is not supported with tools + stream`, so 5xx is included.
    RETRYABLE_STATUS = (400, 404, 422, 500, 501, 502)

    #: `base_url|model` → index of the first payload rung that worked. What a
    #: server accepts does not change between turns, so remembering it saves a
    #: guaranteed-to-fail round trip on every following request.
    _payload_memory: dict[str, int] = {}

    def __init__(self, base_url: str, api_key: str = "", model: str = "",
                 transport: httpx.AsyncBaseTransport | None = None,
                 extra_body: dict[str, Any] | None = None) -> None:
        self.base_url = normalize_openai_base_url(base_url)
        self.api_key = api_key
        self.model = model
        self.transport = transport
        # Provider-specific extras (e.g. llama.cpp/vLLM `chat_template_kwargs`).
        self.extra_body: dict[str, Any] = dict(extra_body or {})

    @classmethod
    def reset_payload_memory(cls) -> None:
        """Forget which payload rung each server accepted (tests, config change)."""
        cls._payload_memory.clear()

    def model_label(self) -> str:
        return self.model or "openai"

    def request_url(self) -> str:
        return chat_completions_url(self.base_url)

    def _headers(self) -> dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def _payload(self, messages, tools, temperature, max_tokens, logprobs,
                 top_logprobs, *, stream_options: bool = True,
                 want_logprobs: bool = True, with_extras: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if stream_options:
            # Some third-party gateways reject this key → see the retry below.
            payload["stream_options"] = {"include_usage": True}
        if tools:
            payload["tools"] = tools
        if logprobs and want_logprobs:
            payload["logprobs"] = True
            payload["top_logprobs"] = top_logprobs
        if with_extras:
            # Provider extras (llama.cpp/vLLM `chat_template_kwargs`): dropped on
            # the last retry because a chat template without an
            # `enable_thinking` switch answers HTTP 400 on it.
            payload.update(self.extra_body)
        return payload

    async def stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        logprobs: bool = False,
        top_logprobs: int = 4,
    ) -> AsyncIterator[StreamEvent]:
        parser = _ThinkParser()
        tool_acc: dict[int, dict[str, Any]] = {}
        finish_reason: str | None = None

        # Retry ladder for gateways that reject parts of the payload:
        #   1. full          — stream_options + logprobs + provider extras
        #   2. no usage/lp   — drop `stream_options` / `logprobs` (HTTP 400/422)
        #   3. bare          — also drop `chat_template_kwargs` (a chat template
        #      that has no `enable_thinking` switch makes llama.cpp answer 400)
        attempts = [
            ("penuh", self._payload(messages, tools, temperature, max_tokens,
                                    logprobs, top_logprobs)),
            ("tanpa stream_options/logprobs",
             self._payload(messages, tools, temperature, max_tokens, logprobs,
                           top_logprobs, stream_options=False,
                           want_logprobs=False)),
            ("payload minimal",
             self._payload(messages, tools, temperature, max_tokens, logprobs,
                           top_logprobs, stream_options=False,
                           want_logprobs=False, with_extras=False)),
        ]

        # Skip the rungs this server already rejected on an earlier turn.
        memory_key = f"{self.base_url}|{self.model}"
        start = self._payload_memory.get(memory_key, 0)
        if start >= len(attempts):
            start = len(attempts) - 1
        attempts = attempts[start:]

        timeout = httpx.Timeout(connect=15.0, read=None, write=30.0, pool=15.0)
        try:
            async with httpx.AsyncClient(timeout=timeout,
                                         transport=self.transport) as client:
                for attempt, (label, payload) in enumerate(attempts, start=start):
                    async with client.stream(
                        "POST", self.request_url(), json=payload,
                        headers=self._headers(),
                    ) as resp:
                        if resp.status_code != 200:
                            body = (await resp.aread()).decode("utf-8", "replace")
                            nxt = attempt - start + 1
                            if nxt < len(attempts) and resp.status_code in \
                                    self.RETRYABLE_STATUS:
                                yield StreamEvent(
                                    "note",
                                    {
                                        "message": (
                                            f"{resp.status_code} dari "
                                            f"{self.request_url()} dengan payload "
                                            f"{label} — mencoba ulang: "
                                            f"{attempts[nxt][0]}"
                                        ),
                                        "status": resp.status_code,
                                        "payload": label,
                                        "detail": body[:300],
                                    },
                                )
                                continue
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
                                        yield StreamEvent(
                                            "thinking", {"text": chunk})
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
                    # This rung works for this server — remember it so later
                    # turns do not repeat a request that is bound to fail.
                    self._payload_memory[memory_key] = attempt
                    break  # stream consumed successfully
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
