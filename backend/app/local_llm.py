"""Local llama.cpp runtime: run a downloaded GGUF as an OpenAI-compatible server.

The offline flow is: pick a model in the catalog → it downloads into the
project's `models/` folder → `runtime.start()` launches `llama-server` on that
file and points the HuggingFace provider at it, so the very next chat (thinking
included) runs fully offline.
"""
from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

import httpx

from .config import PROJECT_ROOT, settings
from .providers.url_utils import models_url, normalize_openai_base_url

INSTALL_HINT = (
    "llama-server belum ditemukan. Install llama.cpp lalu coba lagi:\n"
    "  macOS      : brew install llama.cpp\n"
    " Ubuntu/Debian: sudo apt install llama.cpp   (atau build dari sumber)\n"
    " Windows    : unduh release llama.cpp (llama-server.exe)\n"
    "  build      : https://github.com/ggml-org/llama.cpp\n"
    "Atau set ASK_LLAMA_SERVER_BIN=/path/ke/llama-server."
)


def find_binary() -> str | None:
    if settings.llama_server_bin:
        p = Path(settings.llama_server_bin).expanduser()
        return str(p) if p.is_file() else shutil.which(str(p))
    found = shutil.which("llama-server")
    if found:
        return found
    for candidate in (
        PROJECT_ROOT / "llama.cpp" / "build" / "bin" / "llama-server",
        Path("/opt/homebrew/bin/llama-server"),
        Path("/usr/local/bin/llama-server"),
    ):
        if candidate.is_file():
            return str(candidate)
    return None


class LocalLLMRuntime:
    """Supervises at most one `llama-server` process."""

    def __init__(self) -> None:
        self.proc: subprocess.Popen | None = None
        self.model_path: str | None = None
        self.port: int | None = None
        self.started_at: float | None = None
        self.error: str | None = None

    # ------------------------------------------------------------------ utils
    @property
    def base_url(self) -> str:
        if self.port is None:
            return ""
        return f"http://127.0.0.1:{self.port}/v1"

    @property
    def log_path(self) -> Path:
        return PROJECT_ROOT / "data" / "llama-server.log"

    def alive(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def build_command(self, model_path: str, port: int, ctx: int,
                      gpu_layers: int, binary: str | None = None) -> list[str]:
        cmd = [
            binary or find_binary() or "llama-server",
            "-m", str(model_path),
            "--host", "127.0.0.1",
            "--port", str(port),
            "-c", str(ctx),
            "--jinja",          # chat template + tool calling
            "--log-disable",
        ]
        if gpu_layers and gpu_layers > 0:
            cmd += ["-ngl", str(gpu_layers)]
        extra = (settings.llama_extra_args or "").split()
        return cmd + extra

    def status(self) -> dict[str, Any]:
        return {
            "binary": find_binary(),
            "available": find_binary() is not None,
            "running": self.alive(),
            "pid": self.proc.pid if self.alive() else None,
            "model_path": self.model_path,
            "port": self.port,
            "base_url": self.base_url,
            "started_at": self.started_at,
            "error": self.error,
            "install_hint": None if find_binary() else INSTALL_HINT,
        }

    # ------------------------------------------------------------------ start
    async def start(self, model_path: str, port: int | None = None,
                    ctx: int | None = None, gpu_layers: int | None = None,
                    wait: float = 180.0) -> dict[str, Any]:
        binary = find_binary()
        if binary is None:
            self.error = INSTALL_HINT
            raise RuntimeError(INSTALL_HINT)
        path = Path(model_path).expanduser()
        if not path.is_file():
            raise FileNotFoundError(f"GGUF tidak ditemukan: {path}")

        await self.stop()

        port = port or settings.hf_port
        ctx = ctx or settings.hf_ctx_size
        gpu_layers = settings.hf_gpu_layers if gpu_layers is None else gpu_layers
        cmd = self.build_command(str(path), port, ctx, gpu_layers, binary)

        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        log = self.log_path.open("w")
        env = os.environ.copy()
        env.setdefault("LLAMA_LOG_COLORS", "0")
        self.proc = subprocess.Popen(
            cmd, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
            env=env, cwd=str(PROJECT_ROOT),
        )
        self.model_path = str(path)
        self.port = port
        self.started_at = time.time()
        self.error = None

        deadline = time.time() + wait
        url = models_url(f"http://127.0.0.1:{port}/v1")
        while time.time() < deadline:
            if self.proc.poll() is not None:
                self.error = (f"llama-server keluar (code {self.proc.returncode}). "
                              f"Log: {self.log_path} — "
                              f"{self._log_tail()}")
                raise RuntimeError(self.error)
            try:
                async with httpx.AsyncClient(timeout=2.0) as client:
                    r = await client.get(url)
                if r.status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            await asyncio.sleep(1.0)
        else:
            self.error = (f"llama-server belum siap dalam {wait:.0f}s "
                          f"(log: {self.log_path})")
            raise RuntimeError(self.error)

        # Provider now talks to the local server we just started.
        from .config import update_settings

        update_settings(
            provider="huggingface",
            hf_base_url=normalize_openai_base_url(self.base_url),
            hf_model=path.name,
        )
        return self.status()

    async def stop(self) -> bool:
        proc, self.proc = self.proc, None
        if proc is None or proc.poll() is not None:
            return False
        proc.terminate()
        for _ in range(20):
            if proc.poll() is not None:
                break
            await asyncio.sleep(0.25)
        if proc.poll() is None:
            proc.kill()
        self.model_path = None
        self.port = None
        self.started_at = None
        return True

    def _log_tail(self, lines: int = 6) -> str:
        try:
            text = self.log_path.read_text(errors="replace").strip().splitlines()
            return " | ".join(text[-lines:])
        except OSError:
            return "(log kosong)"


runtime = LocalLLMRuntime()
