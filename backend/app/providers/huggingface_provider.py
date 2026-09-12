"""HuggingFace local provider.

Runs against any OpenAI-compatible server hosting a HuggingFace model —
the recommended setup on a laptop is llama.cpp `llama-server` serving a GGUF
quant from the HF Hub (see `app/hf_models.py` for the 8 GB-friendly catalog
that downloads straight into the project's `models/` folder), which gives
native tool-calling + streaming logprobs for the mechanistic interpreter.

`settings.thinking` is forwarded as `chat_template_kwargs.enable_thinking`,
the switch Qwen3-style chat templates honour — so the reasoning stream shown
in the *Mechanistic Interpreter* panel can be switched per model.
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
        return f"{self.model} (local)"
