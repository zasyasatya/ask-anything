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
from .tools.args import repair_arguments

THINK = THINK_TAGS
TOOL_CALL = TOOL_CALL_TAGS
TOOL_KIND = "tool_call"

#: `pip install -r backend/requirements-local.txt`
INSTALL_HINT = (
    "Inference lokal butuh PyTorch + transformers yang benar-benar bisa "
    "dijalankan, dan environment ini belum memenuhinya. Jalankan:\n"
    "  python run.py --install-local\n"
    "  (memverifikasi torch; bila instalasi rusak — mis. Windows OSError "
    "WinError 1114 pada c10.dll — ia mendeteksi dan pasang ulang otomatis)\n"
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
            # Model lokal sering menulis argumen hampir-JSON; perbaiki di satu
            # tempat (backend/app/tools/args.py) alih-alih menyerahkan
            # {"_raw": ...} ke tool.
            args = repair_arguments(args)
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
        self.max_position: int = 0
        self.state: str = "idle"        # idle | loading | ready | error
        self.error: str | None = None
        self.loaded_at: float | None = None
        self.generating = False
        self._lock: asyncio.Lock | None = None
        self._lock_loop: asyncio.AbstractEventLoop | None = None
        self._task: asyncio.Task | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._scheduled = False
        self._gen_lock = threading.Lock()

    def bind_loop(self, loop: asyncio.AbstractEventLoop | None = None) -> None:
        """Ingat event loop aplikasi agar `start_load` bisa dipanggil dari thread.

        Autoload model sengaja berjalan di thread daemon (lihat
        `main._run_autoload_in_background`) supaya startup tidak tersandera
        pemindaian folder `models/`. Thread itu tidak punya event loop, jadi
        `asyncio.create_task` di sana gagal dengan `RuntimeError: no running
        event loop` — dulu itu membuat model lokal **tidak pernah** ter-autoload
        (gejalanya tertutup oleh error DLL torch). Loop yang di-bind di
        `lifespan` dipakai sebagai target penjadwalan.
        """
        self._loop = loop or asyncio.get_running_loop()

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
        elif self.state == "loading":
            label = self.repo_id or (Path(self.model_path).name
                                     if self.model_path else "model")
            hint = (f"Memuat {label} ke memori — beberapa detik hingga "
                    "puluhan detik tergantung ukuran model & mesin. "
                    "Chat yang dikirim sekarang akan otomatis menunggu.")
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
            "max_position": self.max_position,
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
        if self._scheduled:
            return self.status()

        coro = self.load(model_path, device, dtype)

        def _log_failure(task: asyncio.Task) -> None:
            # Kegagalan load sudah disimpan di `state`/`error` (UI mem-poll
            # status); callback ini memastikan exception task tidak mengambang
            # ("Task exception was never retrieved") di log server.
            if task.cancelled():
                return
            exc = task.exception()
            if exc is not None:
                print(f"[local-inference] load gagal: {exc}", flush=True)

        def _spawn() -> None:
            # Dijalankan **di dalam** loop target, jadi task-nya melekat pada
            # loop yang sama dengan request handler — `wait_load()` bisa
            # menunggunya tanpa "attached to a different loop".
            self._scheduled = False
            self._task = asyncio.create_task(coro)
            self._task.add_done_callback(_log_failure)

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            loop = self._loop
            if loop is None or loop.is_closed():
                coro.close()
                raise RuntimeError(
                    "engine belum terikat ke event loop: panggil "
                    "engine.bind_loop() saat startup, atau jalankan "
                    "start_load() dari dalam event loop."
                ) from None
            self._scheduled = True
            self._set_state("loading", model_path=str(model_path), error=None)
            loop.call_soon_threadsafe(_spawn)
            return self.status()

        _spawn()
        return self.status()

    async def wait_load(self, timeout: float | None = None) -> dict[str, Any]:
        """Await a background load (used by run.py / tests)."""
        deadline = None if timeout is None else time.monotonic() + timeout
        # `start_load()` dari thread lain menjadwalkan pembuatan task lewat
        # `call_soon_threadsafe`, jadi sesaat `_task` masih None walau state
        # sudah "loading" — tunggu task-nya muncul dulu.
        while self._scheduled and self._task is None:
            if deadline is not None and time.monotonic() >= deadline:
                raise asyncio.TimeoutError
            await asyncio.sleep(0.01)
        if self._task is not None:
            remaining = None if deadline is None else max(
                0.0, deadline - time.monotonic())
            await asyncio.wait_for(asyncio.shield(self._task), remaining)
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
            self.max_position = int(loaded.get("max_position") or 0)
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
        if torch_dtype in ("float16", "half") and device == "cpu":
            torch_dtype = "bfloat16"   # fp16 matmul on CPU is painfully slow
        elif torch_dtype == "auto" and device == "cpu":
            # Repo-model Qwen2/3, Llama-3.2, dsb. menyimpan bobot asli bf16;
            # memuat bf16 di CPU memangkas RAM ±50% dibanding fp32 tanpa
            # kehilangan kualitas berarti untuk model <3B — penting di mesin
            # 4–8 GB yang menjalankan 0.5B/1.7B.
            torch_dtype = "bfloat16"

        kwargs: dict[str, Any] = {"trust_remote_code": trust_remote,
                                  "low_cpu_mem_usage": True}
        # Setiap generasi transformers menerima nama argumen dtype yang
        # berbeda (≥4.56: `dtype`, sebelumnya: `torch_dtype`, beberapa versi
        # hanya satu di antaranya) — coba semuanya supaya SEMUA model bisa
        # dimuat, lalu terakhir tanpa dtype (fallback fp32/bobot asli).
        model = None
        last_error: Exception | None = None
        for attempt in ({"dtype": torch_dtype},
                        {"torch_dtype": torch_dtype},
                        {}):
            try:
                model = AutoModelForCausalLM.from_pretrained(
                    str(path), **attempt, **kwargs)
                break
            except (TypeError, ValueError, KeyError) as exc:
                last_error = exc
        if model is None:
            raise last_error if last_error is not None else RuntimeError(
                "gagal memuat model dari folder")

        model = model.to(device)
        model.eval()
        params = sum(p.numel() for p in model.parameters())
        # Batas konteks model ini: prompt yang melebihi batas akan membuat
        # generate() salah (attention mask tidak valid / crash), jadi stream()
        # men-truncate riwayat ke angka ini — model berapapun konteksnya tetap
        # bisa dipakai.
        cfg = getattr(model, "config", None)
        max_position = (getattr(cfg, "max_position_embeddings", None)
                        or getattr(cfg, "max_sequence_length", None)
                        or getattr(cfg, "model_max_length", None))
        try:
            max_position = int(max_position)
        except (TypeError, ValueError):
            max_position = 0
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
                "params": int(params), "repo_id": repo_id or path.name,
                "max_position": max_position}

    async def unload(self) -> bool:
        async with self._mutex():
            had = self.model is not None
            self.model = None
            self.tokenizer = None
            self.model_path = None
            self.repo_id = None
            self.params = None
            self.max_position = 0
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

        pad = self.tokenizer.pad_token_id or self.tokenizer.eos_token_id
        kwargs: dict[str, Any] = {
            "max_new_tokens": int(max_new_tokens),
            "streamer": streamer,
            "do_sample": temperature > 0,
            "stopping_criteria": StoppingCriteriaList([_Stop()]),
        }
        if pad is not None:
            kwargs["pad_token_id"] = pad
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

        # Truncate bila prompt melebihi batas konteks model: riwayat
        # percakapan yang panjang boleh membuat model kecil (mis. 512 token)
        # melampaui batasnya — bukannya error, riwayat terlama yang dipangkas.
        def _tokenize(truncate_to: int | None) -> Any:
            args: dict[str, Any] = {"return_tensors": "pt"}
            if truncate_to and truncate_to > 0:
                # `truncation` hanya menerima TruncationStrategy
                # (`longest_first`/`only_first`/…); sisi pemangkasan diatur
                # lewat `truncation_side`. Mengirim `truncation="left"`
                # membuat transformers melempar ValueError sehingga chat
                # gagal total begitu prompt melewati batas konteks.
                previous_side = getattr(self.tokenizer, "truncation_side", "right")
                try:
                    self.tokenizer.truncation_side = "left"  # buang riwayat terlama
                    args.update({"truncation": True, "max_length": truncate_to})
                    return self.tokenizer(prompt, **args)
                finally:
                    self.tokenizer.truncation_side = previous_side
            return self.tokenizer(prompt, **args)

        try:
            inputs = _tokenize(None)
            prompt_tokens = int(inputs["input_ids"].shape[-1])
            limit = self.max_position
            if limit and prompt_tokens >= limit:
                keep = max(limit - 64, 8)   # sisakan ruang utk jawaban
                inputs = _tokenize(keep)
                prompt_tokens = int(inputs["input_ids"].shape[-1])
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
        except Exception as exc:  # noqa: BLE001
            yield StreamEvent("error", {
                "message": f"tokenisasi gagal: {type(exc).__name__}: {exc}"})
            return

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
