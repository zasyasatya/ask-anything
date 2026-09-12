"""HuggingFace local provider.

Runs against any OpenAI-compatible server hosting a HuggingFace model —
the recommended setup on a 16 GB laptop is llama.cpp `llama-server` serving a
GGUF quant from the HF Hub (default: Qwen/Qwen3-8B-GGUF Q4_K_M), which gives
native tool-calling + streaming logprobs for the mechanistic interpreter.
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
        )

    def model_label(self) -> str:
        return f"{self.model} (local)"
