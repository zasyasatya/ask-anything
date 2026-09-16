"""HuggingFace **local** provider: inference langsung di proses backend.

Dipakai ketika `provider=huggingface` dan `hf_mode=local` (default). Model-nya
adalah folder hasil download dari HuggingFace Hub (`models/<org>/<name>`,
lihat `app/hf_hub.py`) yang di-load `app/local_inference.py` dengan
`transformers` — tanpa llama.cpp, tanpa server sampingan.

Provider ini hanya adapter tipis: semua kerja (tokenisasi, generate, parsing
tool call) ada di engine, sehingga provider remote dan lokal menghasilkan
`StreamEvent` yang identik untuk agent loop.
"""
from __future__ import annotations

from typing import Any, AsyncIterator

from ..config import Settings
from .base import BaseProvider, StreamEvent


def _engine():
    """Import engine-nya di sini: `app.local_inference` meng-import
    `app.providers.base`, jadi import di level modul akan berputar."""
    from ..local_inference import engine
    return engine


class HFLocalProvider(BaseProvider):
    name = "huggingface"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.model = (settings.hf_model or "").strip()

    def model_label(self) -> str:
        return f"{self.model or 'model lokal'} (lokal)"

    async def stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        logprobs: bool = False,
        top_logprobs: int = 4,
    ) -> AsyncIterator[StreamEvent]:
        engine = _engine()
        if not engine.ready() and engine.state == "loading":
            # User mengirim chat sambil model masih di-load: jangan
            # jawab error — tunggu sampai siap (dengan batasan waktu) dan
            # beri tahu UI-nya lewat event note.
            yield StreamEvent("note", {
                "message": ("model masih dimuat ke memori — menunggu sampai "
                            "siap sebelum mulai menjawab"),
                "status": "loading",
            })
            try:
                await engine.wait_load(timeout=900)
            except Exception:  # noqa: BLE001 - timeout/kegagalan ditangani di bawah
                pass
            if not engine.ready():
                status = engine.status()
                yield StreamEvent("error", {
                    "message": (status.get("error")
                                or status.get("hint")
                                or "model lokal belum bisa dimuat"),
                    "status": None,
                    "hint": status.get("hint"),
                })
                return
        if not engine.ready():
            yield StreamEvent("error", {
                "message": (engine.status().get("error")
                            or engine.status().get("hint")
                            or "model lokal belum di-load"),
                "status": None,
                "hint": ("Buka Settings → Model offline (HuggingFace), unduh "
                         "sebuah model, lalu klik **Pakai & muat**."),
            })
            return

        async for ev in engine.stream(
            messages, tools, temperature=temperature, max_new_tokens=max_tokens,
            thinking=bool(self.settings.thinking),
        ):
            yield ev
