"""Local HuggingFace inference: run a downloaded model *in this process*.

No llama.cpp, no side server. A model downloaded into the project's `models/`
folder (see `app/hf_hub.py`) is loaded with `transformers` and streamed token by
token through the same `StreamEvent` protocol the remote providers use, so the
agent loop, the tools and the Mechanistic Interpreter behave identically
offline.

Heavy work (weight loading, `model.generate`) runs in worker threads; the async
side only reads the `TextIteratorStreamer` queue, so the FastAPI event loop
stays responsive while a model generates.

`torch` / `transformers` are *optional* dependencies: when they are missing the
engine reports an actionable install hint instead of breaking the app, and the
other providers (OpenAI-compatible API, mock) keep working.
"""
from __future__ import annotations

import asyncio
import importlib
import json
import re
import threading
import time
from pathlib import Path
from typing import Any, AsyncIterator

from .providers.base import StreamEvent, ToolCall
from .streamtags import TEXT, THINK_TAGS, TOOL_CALL_TAGS, TagStreamParser

THINK = THINK_TAGS
TOOL_CALL = TOOL_CALL_TAGS
TOOL_KIND = "tool_call"

#: `pip install -r backend/requirements-local.txt`
INSTALL_HINT = (
    "Inference lokal butuh PyTorch + transformers, yang belum ter-install di "
    "environment ini. Jalankan:\n"
    "  python run.py --install-local\n"
    "atau langsung:\n"
    "  .venv/bin/pip install -r backend/requirements-local.txt\n"
    "(CPU saja: tambahkan --index-url https://download.pytorch.org/whl/cpu)\n"
    "Tanpa itu, mode `mock` dan provider OpenAI-compatible tetap bisa dipakai."
)

_END = object()


def dependencies() -> dict[str, Any]:
    """Import status of the optional local-inference stack (never raises)."""
    info: dict[str, Any] = {"available": False, "torch": None,
                            "transformers": None, "device": None,
                            "install_hint": None}
    try:
        torch = importlib.import_module("torch")
        tf = importlib.import_module("transformers")
    except Exception as exc:  # noqa: BLE001 - optional dependency
        info["install_hint"] = f"{INSTALL_HINT}\n(detail: {type(exc).__name__}: {exc})"
        return info

    info["torch"] = getattr(torch, "__version__", "?")
    info["transformers"] = getattr(tf, "__version__", "?")
    if torch.cuda.is_available():
        info["device"] = f"cuda ({torch.cuda.get_device_name(0)})"
    elif getattr(getattr(torch, "backends", None), "mps", None) and \
            torch.backends.mps.is_available():
        info["device"] = "mps (Apple Silicon)"
    else:
        info["device"] = "cpu"
    info["available"] = True
    return info


def _friendly(message: str) -> str:
    """Translate the most common local-load failures into something actionable."""
    lowered = message.lower()
    if "outofmemory" in lowered or "out of memory" in lowered or "cuda" in lowered \
            and "memory" in lowered:
        return ("Memori tidak cukup untuk model ini. Pilih model yang lebih kecil, "
                "atau set ASK_HF_DEVICE=cpu / ASK_HF_DTYPE=float16.\n" + message)
    if "trust_remote_code" in lowered:
        return ("Model ini butuh kode kustom dari repo-nya. Set "
                "ASK_HF_TRUST_REMOTE_CODE=1 bila Anda mempercayai repo tersebut.\n"
                + message)
    if "safetensors" in lowered or "does not appear to have a file named" in lowered:
        return ("File model tidak lengkap (weights hilang/rusak). Hapus modelnya "
                "lalu unduh ulang.\n" + message)
    return message


def _json_objects(text: str) -> list[Any]:
    """Every top-level JSON object/array found in `text` (tolerant scan)."""
    out: list[Any] = []
    for match in re.finditer(r"[\[{]", text):
        try:
            obj, _ = json.JSONDecoder().raw_decode(text, match.start())
        except ValueError:
            continue
        if isinstance(obj, (dict, list)):
            out.append(obj)
    return out


def _looks_like_call(obj: Any) -> bool:
    return (isinstance(obj, dict) and isinstance(obj.get("name"), str)
            and bool(obj["name"].strip()) and "arguments" in obj)


def extract_tool_calls(text: str) -> tuple[list[ToolCall], str]:
    """Pull tool calls out of a local model's output.

    Handles the shapes real chat templates emit:

        <tool_response>{"name": "web_search", "arguments": {"query": "x"}}</tool_response>
        <tool_response>{"name": "calc", "arguments": {"expression": "1+1"}}</tool_response>
        [{"name": "web_search", "arguments": {"query": "x"}}]      (Llama-3.1)

    Returns `(calls, answer_text)`; the call blocks are removed from the answer
    so the user never sees raw JSON.
    """
    calls: list[ToolCall] = []
    cleaned = text

    def add(obj: Any) -> bool:
        args = obj.get("arguments")
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except ValueError:
                args = {"_raw": args}
        if not isinstance(args, dict):
            args = {"value": args}
        calls.append(ToolCall(id=f"call_{len(calls) + 1}",
                              name=str(obj["name"]).strip(), arguments=args))
        return True

    for block in re.findall(re.escape(TOOL_CALL[0]) + r"(.*?)"
                            + re.escape(TOOL_CALL[1]), text, re.S):
        for obj in _json_objects(block):
            if _looks_like_call(obj):
                add(obj)
            elif isinstance(obj, list):
                for item in obj:
                    if _looks_like_call(item):
                        add(item)
        cleaned = cleaned.replace(
            f"{TOOL_CALL[0]}{block}{TOOL_CALL[1]}", " ")

    if not calls:
        # No tags: templates like Llama-3.1 emit a bare JSON array.
        for obj in _json_objects(text):
            candidates = obj if isinstance(obj, list) else [obj]
            if all(_looks_like_call(c) for c in candidates) and candidates:
                for item in candidates:
                    add(item)
                cleaned = " ".join(
                    part for part in re.split(r"[\[{].*?[\]}]", cleaned, flags=re.S)
                )
                break

    return calls, cleaned.strip()


class LocalInferenceEngine:
    """Supervises at most one locally loaded model."""

    def __init__(self) -> None:
        self.model: Any = None
        self.tokenizer: Any = None
        self.model_path: str | None = None
        self.repo_id: str | None = None
        self.device: str = ""
        self.dtype: str = ""
        self.params: int | None = None
        self.state: str = "idle"        # idle | loading | ready | error
        self.error: str | None = None
        self.loaded_at: float | None = None
        self.generating = False
        self._lock: asyncio.Lock | None = None
        self._lock_loop: asyncio.AbstractEventLoop | None = None
        self._task: asyncio.Task | None = None
        self._gen_lock = threading.Lock()

    def _mutex(self) -> asyncio.Lock:
        """`asyncio.Lock` is bound to the loop that first uses it — a reloaded
        app (or a test suite) runs a fresh loop, so rebuild it when needed."""
        loop = asyncio.get_running_loop()
        if self._lock is None or self._lock_loop is not loop:
            self._lock = asyncio.Lock()
            self._lock_loop = loop
        return self._lock

    # ------------------------------------------------------------------ state
    @property
    def settings(self):  # local import keeps `config` free of engine imports
        from .config import settings
        return settings

    def ready(self) -> bool:
        return self.state == "ready" and self.model is not None

    def status(self) -> dict[str, Any]:
        deps = dependencies()
        hint = None
        if not deps["available"]:
            hint = deps["install_hint"]
        elif self.state == "idle" and not self.model_path:
            hint = ("Belum ada model yang dimuat. Buka Settings → Model offline "
                    "(HuggingFace), cari model di HuggingFace, unduh, lalu klik "
                    "**Pakai & muat**.")
        return {
            "state": self.state,
            "running": self.ready(),
            "available": deps["available"],
            "deps": deps,
            "model_path": self.model_path,
            "repo_id": self.repo_id,
            "model_label": self.repo_id or (Path(self.model_path).name
                                            if self.model_path else None),
            "device": self.device or deps.get("device"),
            "dtype": self.dtype,
            "params": self.params,
            "loaded_at": self.loaded_at,
            "generating": self.generating,
            "error": self.error,
            "hint": self.error or hint,
            "install_hint": None if deps["available"] else INSTALL_HINT,
        }

    def _set_state(self, state: str, **kw: Any) -> None:
        self.state = state
        for key, value in kw.items():
            setattr(self, key, value)

    # ------------------------------------------------------------------- load
    def start_load(self, model_path: str | Path, device: str | None = None,
                   dtype: str | None = None) -> dict[str, Any]:
        """Load in the background and return at once (the UI polls status).

        Loading a multi-gigabyte checkpoint takes tens of seconds; an HTTP
        request must not block on it.
        """
        if self._task is not None and not self._task.done():
            return self.status()
        self._task = asyncio.create_task(self.load(model_path, device, dtype))
        return self.status()

    async def wait_load(self, timeout: float | None = None) -> dict[str, Any]:
        """Await a background load (used by run.py / tests)."""
        if self._task is not None:
            await asyncio.wait_for(asyncio.shield(self._task), timeout)
        return self.status()

    async def load(self, model_path: str | Path, device: str | None = None,
                   dtype: str | None = None) -> dict[str, Any]:
        """Load a downloaded model folder. Safe to call again to swap models."""
        deps = dependencies()
        if not deps["available"]:
            self.error = deps["install_hint"]
            raise RuntimeError(self.error)

        path = Path(model_path).expanduser()
        if not (path / "config.json").is_file():
            raise FileNotFoundError(
                f"bukan folder model HuggingFace (config.json tidak ada): {path}")

        async with self._mutex():
            self._set_state("loading", model_path=str(path), error=None)
            try:
                loaded = await asyncio.to_thread(
                    self._load_sync, path, device, dtype,
                    self.settings.hf_threads)
            except Exception as exc:  # noqa: BLE001 - surfaced to the UI
                message = f"{type(exc).__name__}: {exc}"
                self._set_state("error", error=_friendly(message),
                                model_path=str(path))
                raise RuntimeError(self.error) from exc

            self.model = loaded["model"]
            self.tokenizer = loaded["tokenizer"]
            self.device = loaded["device"]
            self.dtype = loaded["dtype"]
            self.params = loaded["params"]
            self.repo_id = loaded["repo_id"]
            self.loaded_at = time.time()
            self._set_state("ready", error=None)
            return self.status()

    def _load_sync(self, path: Path, device: str | None, dtype: str | None,
                   threads: int) -> dict[str, Any]:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        trust_remote = bool(getattr(self.settings, "hf_trust_remote_code", False))
        if device in (None, "", "auto"):
            if torch.cuda.is_available():
                device = "cuda"
            elif getattr(getattr(torch, "backends", None), "mps", None) and \
                    torch.backends.mps.is_available():
                device = "mps"
            else:
                device = "cpu"
        if threads and threads > 0:
            torch.set_num_threads(int(threads))

        tokenizer = AutoTokenizer.from_pretrained(
            str(path), trust_remote_code=trust_remote)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        want = (dtype or self.settings.hf_dtype or "auto").strip() or "auto"
        torch_dtype = want
        if want == "float16" and device == "cpu":
            torch_dtype = "bfloat16"   # fp16 matmul on CPU is painfully slow

        kwargs: dict[str, Any] = {"trust_remote_code": trust_remote,
                                  "low_cpu_mem_usage": True}
        model = None
        last_error: Exception | None = None
        for key in ("dtype", "torch_dtype"):   # transformers ≥4.56 → `dtype`
            try:
                model = AutoModelForCausalLM.from_pretrained(
                    str(path), **{key: torch_dtype}, **kwargs)
                break
            except (TypeError, ValueError) as exc:
                last_error = exc
        if model is None:
            if last_error is not None:
                raise last_error
            model = AutoModelForCausalLM.from_pretrained(str(path), **kwargs)

        model = model.to(device)
        model.eval()
        params = sum(p.numel() for p in model.parameters())
        repo_id = ""
        manifest = path / ".ask-anything.json"
        if manifest.is_file():
            try:
                repo_id = str(json.loads(manifest.read_text("utf-8"))
                              .get("repo_id") or "")
            except ValueError:
                repo_id = ""
        return {"model": model, "tokenizer": tokenizer, "device": device,
                "dtype": str(getattr(model, "dtype", torch_dtype)),
                "params": int(params), "repo_id": repo_id or path.name}

    async def unload(self) -> bool:
        async with self._mutex():
            had = self.model is not None
            self.model = None
            self.tokenizer = None
            self.model_path = None
            self.repo_id = None
            self.params = None
            self.loaded_at = None
            self.error = None
            self.state = "idle"
        if had:
            await asyncio.to_thread(self._clear_cuda)
        return had

    @staticmethod
    def _clear_cuda() -> None:
        try:
            import gc

            import torch
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:  # noqa: BLE001 - best effort
            pass

    # ------------------------------------------------------------- generation
    def _render(self, messages: list[dict[str, Any]],
                tools: list[dict[str, Any]], thinking: bool) -> str:
        """Chat template → prompt string (tools & enable_thinking when supported)."""
        tok = self.tokenizer
        clean = [{"role": m.get("role", "user"),
                  "content": m.get("content") or ""}
                 for m in messages if m.get("role") in
                 ("system", "user", "assistant", "tool")]
        kwargs: dict[str, Any] = {"add_generation_prompt": True,
                                  "tokenize": False}
        if tools:
            kwargs["tools"] = tools
        try:
            return tok.apply_chat_template(clean, enable_thinking=bool(thinking),
                                           **kwargs)
        except Exception:  # noqa: BLE001 - template tanpa switch itu
            try:
                return tok.apply_chat_template(clean, **kwargs)
            except Exception:  # noqa: BLE001 - template tanpa dukungan tools
                kwargs.pop("tools", None)
                return tok.apply_chat_template(clean, **kwargs)

    def _eos_ids(self) -> list[int]:
        ids: list[int] = []
        for source in (getattr(self.tokenizer, "eos_token_id", None),
                       getattr(getattr(self.model, "generation_config", None),
                               "eos_token_id", None)):
            if isinstance(source, (list, tuple)):
                ids.extend(int(i) for i in source if i is not None)
            elif source is not None:
                ids.append(int(source))
        return sorted(set(ids))

    def _generate_thread(self, inputs: Any, streamer: Any, temperature: float,
                         max_new_tokens: int, stop: threading.Event) -> None:
        import torch
        from transformers import StoppingCriteria, StoppingCriteriaList

        engine = self

        class _Stop(StoppingCriteria):
            def __call__(self, input_ids, scores, **kwargs) -> bool:
                return stop.is_set()

        kwargs: dict[str, Any] = {
            "max_new_tokens": int(max_new_tokens),
            "streamer": streamer,
            "do_sample": temperature > 0,
            "pad_token_id": self.tokenizer.pad_token_id
            or self.tokenizer.eos_token_id,
            "stopping_criteria": StoppingCriteriaList([_Stop()]),
        }
        if temperature > 0:
            kwargs["temperature"] = float(temperature)
            kwargs["top_p"] = 0.95
        eos = engine._eos_ids()
        if eos:
            kwargs["eos_token_id"] = eos
        try:
            with torch.inference_mode():
                self.model.generate(**inputs, **kwargs)
        except Exception as exc:  # noqa: BLE001 - reported through the stream
            streamer.end()
            self.error = _friendly(f"{type(exc).__name__}: {exc}")

    async def stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        temperature: float = 0.7,
        max_new_tokens: int = 1024,
        thinking: bool = True,
    ) -> AsyncIterator[StreamEvent]:
        if not self.ready():
            status = self.status()
            yield StreamEvent("error", {
                "message": (self.error or status.get("hint")
                            or "model lokal belum dimuat"),
                "hint": status.get("hint"),
            })
            return

        try:
            prompt = self._render(messages, tools, thinking)
        except Exception as exc:  # noqa: BLE001
            yield StreamEvent("error", {
                "message": f"gagal menyusun prompt dari chat template: {exc}"})
            return

        import torch
        from transformers import TextIteratorStreamer

        try:
            inputs = self.tokenizer(prompt, return_tensors="pt")
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
        except Exception as exc:  # noqa: BLE001
            yield StreamEvent("error", {
                "message": f"tokenisasi gagal: {type(exc).__name__}: {exc}"})
            return

        prompt_tokens = int(inputs["input_ids"].shape[-1])
        streamer = TextIteratorStreamer(self.tokenizer, skip_prompt=True,
                                        skip_special_tokens=True)
        stop = threading.Event()
        worker = threading.Thread(
            target=self._generate_thread,
            args=(inputs, streamer, temperature, max_new_tokens, stop),
            daemon=True,
        )

        parser = TagStreamParser({"think": THINK, TOOL_KIND: TOOL_CALL})
        tool_blocks: list[str] = []
        answer_parts: list[str] = []
        thinking_parts: list[str] = []
        completion_tokens = 0
        started = time.time()
        self.generating = True

        yield StreamEvent("note", {
            "message": (f"inference lokal: {self.repo_id or self.model_path} di "
                        f"{self.device} ({self.dtype}) — {prompt_tokens} token "
                        "prompt"),
            "status": "local",
        })

        try:
            with self._gen_lock:
                worker.start()
                queue: asyncio.Queue = asyncio.Queue()
                loop = asyncio.get_running_loop()

                def _pump() -> None:
                    try:
                        for piece in streamer:
                            loop.call_soon_threadsafe(queue.put_nowait, piece)
                    except Exception as exc:  # noqa: BLE001
                        loop.call_soon_threadsafe(
                            queue.put_nowait,
                            RuntimeError(f"{type(exc).__name__}: {exc}"))
                    finally:
                        loop.call_soon_threadsafe(queue.put_nowait, _END)

                threading.Thread(target=_pump, daemon=True).start()

                while True:
                    item = await queue.get()
                    if item is _END:
                        break
                    if isinstance(item, Exception):
                        yield StreamEvent("error", {"message": str(item)})
                        return
                    completion_tokens += max(1, len(item.split()))
                    for kind, chunk in parser.feed(item):
                        if kind == "think":
                            thinking_parts.append(chunk)
                            yield StreamEvent("thinking", {"text": chunk})
                        elif kind == TOOL_KIND:
                            tool_blocks.append(chunk)
                        elif chunk:
                            answer_parts.append(chunk)
                            yield StreamEvent("delta", {"text": chunk})

                for kind, chunk in parser.flush():
                    if kind == "think":
                        thinking_parts.append(chunk)
                        yield StreamEvent("thinking", {"text": chunk})
                    elif kind == TOOL_KIND:
                        tool_blocks.append(chunk)
                    elif chunk:
                        answer_parts.append(chunk)
                        yield StreamEvent("delta", {"text": chunk})
        finally:
            stop.set()
            self.generating = False

        text = "".join(answer_parts)
        # Tool call bisa datang bertag (di `tool_blocks`) atau sebagai JSON
        # polos di dalam jawaban — dua-duanya dibersihkan dari teks jawaban.
        calls, cleaned = extract_tool_calls("".join(tool_blocks) or text)
        if not tool_blocks and cleaned and cleaned != text:
            yield StreamEvent("note", {
                "message": "blok tool call dibersihkan dari teks jawaban",
                "status": "local",
            })

        if calls:
            yield StreamEvent("tool_calls",
                              {"calls": [c.to_dict() for c in calls]})

        yield StreamEvent("usage", {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "latency_ms": round((time.time() - started) * 1000, 1),
            "device": self.device,
        })
        if self.error:
            yield StreamEvent("error", {"message": self.error})
            self.error = None
            return
        yield StreamEvent("done", {"finish_reason": "tool_calls" if calls
                                   else "stop"})


engine = LocalInferenceEngine()
