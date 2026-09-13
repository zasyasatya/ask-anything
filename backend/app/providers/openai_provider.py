"""OpenAI-protocol client (OpenAI API, LiteLLM/gateway apa pun, vLLM, llama.cpp).

Every OpenAI-compatible server speaks this protocol, but *not* every server
accepts the same payload: gateways reject `stream_options`, some reject
`logprobs`, some reject `tools`, llama.cpp answers **500** with
`logprobs is not supported with tools + stream`, and a chat template without an
`enable_thinking` switch answers **400** on `chat_template_kwargs`.

So the client walks a **retry ladder** (full payload → no stream_options/
logprobs → no extras → no tools) and, if *every* streaming shape is rejected,
falls back to a plain **non-streaming** request — the exact shape of the `curl`
example in most API docs. Meaning: if the user's curl works, the chat works.

Every failure is reported with the server's own words (`error.message`) plus a
hint in Indonesian, so "kenapa error?" is answerable straight from the UI.
"""
from __future__ import annotations

import json
from typing import Any, AsyncIterator

import httpx

from ..streamtags import THINK_TAGS, TOOL_CALL_TAGS, TagStreamParser
from .base import BaseProvider, StreamEvent, ToolCall
from .url_utils import chat_completions_url, normalize_openai_base_url

THINK = "think"
TOOL_KIND = "tool_call"

#: HTTP statuses that mean "this payload shape is not accepted here" rather
#: than "the server is broken".
RETRYABLE_STATUS = (400, 404, 413, 415, 422, 500, 501, 502, 503)


def error_hint(status: int | None, body: str) -> str:
    """Best-effort Indonesian explanation of an API failure."""
    text = (body or "").lower()
    if status in (401, 403) or "authentication" in text or "invalid api key" in text:
        return ("API key ditolak endpoint. Periksa key-nya (dan apakah key itu "
                "untuk base URL ini).")
    if "model_not_found" in text or "does not exist" in text or "no such model" in text:
        return ("Nama model tidak dikenal endpoint ini. Klik **Muat model** dan "
                "pilih nama persis dari daftar yang dikembalikan endpoint.")
    if "logprob" in text:
        return ("Endpoint menolak `logprobs`. Matikan `ASK_LOGPROBS` bila pesan "
                "ini terus muncul.")
    if "context" in text and ("length" in text or "exceed" in text or "token" in text):
        return "Prompt melebihi batas konteks model — perpendek riwayat/pesan."
    if status == 429 or "rate limit" in text or "quota" in text:
        return "Endpoint membatasi laju request (429/quota). Coba lagi sebentar."
    if status == 404:
        return ("URL endpoint salah (404). Base URL harus tanpa "
                "`/chat/completions`, mis. `https://host/v1`.")
    if "tool" in text and status in (400, 422, 500):
        return "Endpoint menolak parameter `tools` pada payload ini."
    if status and status >= 500:
        return "Endpoint menjawab error server (5xx). Coba lagi atau cek log-nya."
    return "Periksa base URL, API key, dan nama model."


class OpenAIProtocolProvider(BaseProvider):
    """Streams chat completions from any OpenAI-compatible endpoint.

    `base_url` may be given in any of the shapes people copy from API docs
    (bare host, `…/v1`, `…/v1/`, or the full `…/v1/chat/completions`); it is
    canonicalised by :mod:`.url_utils` before the endpoint path is appended.
    """

    name = "openai"
    RETRYABLE_STATUS = RETRYABLE_STATUS

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
                 top_logprobs, *, stream: bool = True, stream_options: bool = True,
                 want_logprobs: bool = True, with_extras: bool = True,
                 with_tools: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        payload["stream"] = bool(stream)
        if stream and stream_options:
            # Some third-party gateways reject this key → see the ladder.
            payload["stream_options"] = {"include_usage": True}
        if tools and with_tools:
            payload["tools"] = tools
        if logprobs and want_logprobs and stream:
            payload["logprobs"] = True
            payload["top_logprobs"] = top_logprobs
        if with_extras:
            # Provider extras (llama.cpp/vLLM `chat_template_kwargs`): dropped on
            # a later rung because a chat template without an `enable_thinking`
            # switch answers HTTP 400 on it.
            payload.update(self.extra_body)
        return payload

    def _ladder(self, messages, tools, temperature, max_tokens, logprobs,
                top_logprobs) -> list[tuple[str, dict[str, Any]]]:
        """Streaming payloads, most capable first."""
        make = lambda **kw: self._payload(  # noqa: E731 - readability here
            messages, tools, temperature, max_tokens, logprobs, top_logprobs, **kw)
        return [
            ("penuh", make()),
            ("tanpa stream_options/logprobs",
             make(stream_options=False, want_logprobs=False)),
            ("payload minimal",
             make(stream_options=False, want_logprobs=False, with_extras=False)),
            ("tanpa tools",
             make(stream_options=False, want_logprobs=False, with_extras=False,
                  with_tools=False)),
        ]

    def _plain_ladder(self, messages, tools, temperature, max_tokens
                      ) -> list[tuple[str, dict[str, Any]]]:
        """Last resort: non-streaming, i.e. exactly the documented curl shape."""
        make = lambda **kw: self._payload(  # noqa: E731
            messages, tools, temperature, max_tokens, False, 0, stream=False, **kw)
        return [
            ("non-streaming", make(with_extras=False)),
            ("non-streaming tanpa tools", make(with_extras=False,
                                               with_tools=False)),
        ]

    @staticmethod
    def _server_error(status: int, body: str) -> str:
        try:
            data = json.loads(body)
        except ValueError:
            data = None
        message = ""
        if isinstance(data, dict):
            err = data.get("error")
            if isinstance(err, dict):
                message = str(err.get("message") or "")
            elif isinstance(err, str):
                message = err
            message = message or str(data.get("message") or "")
        detail = message or body[:400]
        hint = error_hint(status, body)
        return f"HTTP {status}: {detail[:400]}\n→ {hint}"

    async def stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        logprobs: bool = False,
        top_logprobs: int = 4,
    ) -> AsyncIterator[StreamEvent]:
        attempts = self._ladder(messages, tools, temperature, max_tokens,
                                logprobs, top_logprobs)

        # Skip the rungs this server already rejected on an earlier turn.
        memory_key = f"{self.base_url}|{self.model}"
        start = min(self._payload_memory.get(memory_key, 0), len(attempts) - 1)
        attempts = attempts[start:]

        timeout = httpx.Timeout(connect=15.0, read=None, write=30.0, pool=15.0)
        last_error = "tidak ada percobaan yang dijalankan"

        try:
            async with httpx.AsyncClient(timeout=timeout,
                                         transport=self.transport) as client:
                for offset, (label, payload) in enumerate(attempts):
                    attempt = start + offset
                    try:
                        async with client.stream(
                            "POST", self.request_url(), json=payload,
                            headers=self._headers(),
                        ) as resp:
                            if resp.status_code != 200:
                                body = (await resp.aread()).decode("utf-8",
                                                                   "replace")
                                last_error = self._server_error(resp.status_code,
                                                                body)
                                hint = error_hint(resp.status_code, body)
                                if resp.status_code not in self.RETRYABLE_STATUS:
                                    # 401/403/429: bentuk payload bukan masalahnya
                                    yield StreamEvent(
                                        "error", {"message": last_error,
                                                  "status": resp.status_code,
                                                  "hint": hint})
                                    return
                                if offset + 1 < len(attempts):
                                    yield StreamEvent("note", {
                                        "message": (
                                            f"{resp.status_code} dari "
                                            f"{self.request_url()} dengan payload "
                                            f"{label} — mencoba ulang: "
                                            f"{attempts[offset + 1][0]}"),
                                        "status": resp.status_code,
                                        "payload": label,
                                        "detail": body[:300],
                                        "hint": hint,
                                    })
                                    continue
                                # Rung terakhir juga ditolak → jatuh ke
                                # fallback non-streaming di bawah loop ini.
                                yield StreamEvent("note", {
                                    "message": (
                                        f"{resp.status_code} dari "
                                        f"{self.request_url()} dengan payload "
                                        f"{label} — semua bentuk streaming "
                                        "ditolak"),
                                    "status": resp.status_code,
                                    "payload": label,
                                    "detail": body[:300],
                                    "hint": hint,
                                })
                                break
                            outcome = None
                            async for ev in self._consume(resp):
                                if ev.type == "error":
                                    outcome = ev
                                    break
                                yield ev
                    except httpx.HTTPError as exc:
                        last_error = f"connection error: {type(exc).__name__}: {exc}"
                        if offset + 1 < len(attempts):
                            yield StreamEvent("note", {
                                "message": f"{last_error} — mencoba ulang: "
                                           f"{attempts[offset + 1][0]}",
                                "status": None, "payload": label,
                            })
                            continue
                        break   # koneksi gagal di semua rung → coba non-streaming

                    if outcome is not None:
                        # 200 OK but the body carried an error (LiteLLM/OpenAI
                        # do this mid-stream) — report it, do not fake success.
                        yield outcome
                        return

                    # This rung works for this server — remember it so later
                    # turns do not repeat a request that is bound to fail.
                    self._payload_memory[memory_key] = attempt
                    return

                # Every streaming shape was rejected → the documented curl
                # shape (non-streaming) is the last thing we can try.
                yield StreamEvent("note", {
                    "message": ("semua bentuk request streaming ditolak "
                                f"({last_error.splitlines()[0]}) — mencoba "
                                "request non-streaming seperti contoh curl"),
                    "status": None, "payload": "fallback non-streaming",
                })
                async for ev in self._non_streaming(client, messages, tools,
                                                    temperature, max_tokens):
                    if ev.type == "error":
                        yield ev
                        return
                    yield ev
                self._payload_memory[memory_key] = len(attempts) + start
        except httpx.HTTPError as exc:
            yield StreamEvent("error",
                              {"message": f"connection error: {exc}"})

    async def _consume(self, resp: httpx.Response) -> AsyncIterator[StreamEvent]:
        """Turn one SSE response into events. An error frame yields `error`."""
        parser = TagStreamParser({THINK: THINK_TAGS, TOOL_KIND: TOOL_CALL_TAGS})
        tool_acc: dict[int, dict[str, Any]] = {}
        finish_reason: str | None = None
        saw_content = False

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

            if isinstance(obj, dict) and obj.get("error"):
                err = obj["error"]
                message = (err.get("message") if isinstance(err, dict)
                           else str(err)) or "error dari endpoint"
                code = err.get("code") if isinstance(err, dict) else None
                yield StreamEvent("error", {
                    "message": f"endpoint mengirim error di dalam stream: "
                               f"{message}\n→ {error_hint(None, str(err))}",
                    "status": code if isinstance(code, int) else 200,
                })
                return

            usage = obj.get("usage")
            if usage:
                yield StreamEvent("usage", {
                    "prompt_tokens": usage.get("prompt_tokens"),
                    "completion_tokens": usage.get("completion_tokens"),
                    "total_tokens": usage.get("total_tokens"),
                })

            choices = obj.get("choices") or []
            if not choices:
                continue
            choice = choices[0]
            delta = choice.get("delta") or {}

            reasoning = delta.get("reasoning_content") or delta.get("reasoning")
            if reasoning:
                yield StreamEvent("thinking", {"text": reasoning})

            content = delta.get("content")
            if content:
                saw_content = True
                for kind, chunk in parser.feed(content):
                    if kind == "think":
                        yield StreamEvent("thinking", {"text": chunk})
                    elif kind == TOOL_KIND:
                        # tool call yang dikirim sebagai teks bertag
                        tool_acc.setdefault(-1, {"id": "", "name": "",
                                                 "arguments": ""})
                        tool_acc[-1]["arguments"] += chunk
                    elif chunk:
                        yield StreamEvent("delta", {"text": chunk})

            lp = choice.get("logprobs")
            if lp and lp.get("content"):
                items = []
                for tok in lp["content"]:
                    items.append({
                        "token": tok.get("token"),
                        "logprob": tok.get("logprob"),
                        "top": [{"token": t.get("token"),
                                 "logprob": t.get("logprob")}
                                for t in tok.get("top_logprobs") or []],
                    })
                yield StreamEvent("logprobs", {"items": items})

            for tc in delta.get("tool_calls") or []:
                idx = tc.get("index", 0)
                slot = tool_acc.setdefault(
                    idx, {"id": "", "name": "", "arguments": ""})
                if tc.get("id"):
                    slot["id"] = tc["id"]
                fn = tc.get("function") or {}
                if fn.get("name"):
                    slot["name"] += fn["name"]
                if fn.get("arguments"):
                    slot["arguments"] += fn["arguments"]

            if choice.get("finish_reason"):
                finish_reason = choice["finish_reason"]

        for kind, chunk in parser.flush():
            if kind == "think":
                yield StreamEvent("thinking", {"text": chunk})
            elif kind == TOOL_KIND:
                tool_acc.setdefault(-1, {"id": "", "name": "", "arguments": ""})
                tool_acc[-1]["arguments"] += chunk
            elif chunk:
                yield StreamEvent("delta", {"text": chunk})

        if tool_acc:
            calls = []
            for idx in sorted(tool_acc):
                slot = tool_acc[idx]
                calls.extend(self._calls_from(slot, idx))
            if calls:
                yield StreamEvent("tool_calls",
                                  {"calls": [c.to_dict() for c in calls]})

        if not saw_content and not tool_acc and finish_reason is None:
            # A 200 with an empty SSE body is a failure users cannot diagnose.
            yield StreamEvent("error", {
                "message": ("endpoint menjawab 200 tetapi tidak mengirim "
                            "isi apa pun (stream kosong)"),
                "status": 200,
            })
            return

        yield StreamEvent("done", {"finish_reason": finish_reason or "stop"})

    @staticmethod
    def _calls_from(slot: dict[str, Any], idx: int) -> list[ToolCall]:
        """Structured tool call, or a tagged JSON blob a local model emitted."""
        raw = slot.get("arguments") or ""
        if slot.get("name"):
            try:
                args = json.loads(raw or "{}")
            except json.JSONDecodeError:
                args = {"_raw": raw}
            return [ToolCall(id=slot["id"] or f"call_{idx}",
                             name=slot["name"], arguments=args)]
        from ..local_inference import extract_tool_calls
        calls, _ = extract_tool_calls(raw)
        return calls

    async def _non_streaming(self, client: httpx.AsyncClient, messages, tools,
                             temperature: float,
                             max_tokens: int) -> AsyncIterator[StreamEvent]:
        """Plain `POST /chat/completions` — the shape from the API docs."""
        last = "request non-streaming tidak dijalankan"
        for label, payload in self._plain_ladder(messages, tools, temperature,
                                                 max_tokens):
            try:
                resp = await client.post(self.request_url(), json=payload,
                                         headers=self._headers())
            except httpx.HTTPError as exc:
                last = f"connection error: {type(exc).__name__}: {exc}"
                continue
            if resp.status_code != 200:
                last = self._server_error(resp.status_code,
                                          resp.text[:600])
                yield StreamEvent("note", {
                    "message": f"{resp.status_code} pada {label} — {last}",
                    "status": resp.status_code, "payload": label,
                    "hint": error_hint(resp.status_code, resp.text),
                })
                continue
            for ev in self._convert_non_stream(resp.text):
                yield ev
            return
        yield StreamEvent("error", {"message": last})

    @staticmethod
    def _convert_non_stream(body: str) -> list[StreamEvent]:
        """A non-streaming chat completion → the same events as the SSE path."""
        try:
            data = json.loads(body)
        except ValueError:
            return [StreamEvent("error", {
                "message": f"jawaban endpoint bukan JSON: {body[:200]}"})]
        if isinstance(data, dict) and data.get("error"):
            err = data["error"]
            message = err.get("message") if isinstance(err, dict) else str(err)
            return [StreamEvent("error", {
                "message": f"endpoint mengirim error: {message}",
                "hint": error_hint(None, str(err))})]

        events: list[StreamEvent] = []
        choices = (data or {}).get("choices") or []
        if choices:
            msg = choices[0].get("message") or {}
            reasoning = msg.get("reasoning_content") or msg.get("reasoning")
            if reasoning:
                events.append(StreamEvent("thinking", {"text": reasoning}))
            content = msg.get("content") or ""
            if content:
                events.append(StreamEvent("delta", {"text": content}))
            raw_calls = msg.get("tool_calls") or []
            calls = []
            for i, tc in enumerate(raw_calls):
                fn = tc.get("function") or {}
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = {"_raw": fn.get("arguments")}
                calls.append(ToolCall(id=tc.get("id") or f"call_{i}",
                                      name=fn.get("name", ""),
                                      arguments=args).to_dict())
            if calls:
                events.append(StreamEvent("tool_calls", {"calls": calls}))
            if not content and not calls:
                events.append(StreamEvent("error", {
                    "message": ("endpoint menjawab 200 tanpa isi "
                                "(choices[0].message kosong)"), "status": 200}))
                return events
        usage = (data or {}).get("usage")
        if usage:
            events.append(StreamEvent("usage", {
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
                "total_tokens": usage.get("total_tokens"),
            }))
        events.append(StreamEvent("note", {
            "message": ("dijawab lewat request non-streaming (fallback karena "
                        "endpoint menolak request streaming)"),
            "status": "fallback",
        }))
        events.append(StreamEvent("done", {
            "finish_reason": (choices[0].get("finish_reason")
                              if choices else "stop") or "stop"}))
        return events
