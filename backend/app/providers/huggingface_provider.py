"""HuggingFace provider — mode `server`.

Dipakai ketika `provider=huggingface` **dan** `hf_mode=server`: model dilayani
oleh server OpenAI-compatible yang Anda jalankan sendiri (vLLM, llama.cpp
`llama-server`, LM Studio, TGI, atau gateway seperti ai.sumopod.com). Untuk
inference langsung di proses backend tanpa server apa pun, pakai mode default
`hf_mode=local` (lihat `app/local_inference.py`).

`settings.thinking` diteruskan sebagai `chat_template_kwargs.enable_thinking`,
switch yang dipahami chat template ala Qwen3 — dan otomatis dibuang oleh retry
ladder bila template model tidak mengenalnya (HTTP 400).
"""
from __future__ import annotations

from ..config import Settings
from .openai_provider import OpenAIProtocolProvider


class HuggingFaceProvider(OpenAIProtocolProvider):
    name = "huggingface"

    def __init__(self, settings: Settings) -> None:
        super().__init__(
            base_url=settings.hf_base_url,
            api_key=settings.hf_api_key,
            model=settings.hf_model,
            extra_body={"chat_template_kwargs":
                        {"enable_thinking": bool(settings.thinking)}},
        )

    def model_label(self) -> str:
        return f"{self.model} (server)"
