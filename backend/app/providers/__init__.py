from ..config import Settings
from .base import BaseProvider, StreamEvent, ToolCall
from .hf_local_provider import HFLocalProvider
from .huggingface_provider import HuggingFaceProvider
from .mock_provider import MockProvider
from .openai_provider import OpenAIProtocolProvider

__all__ = [
    "BaseProvider",
    "StreamEvent",
    "ToolCall",
    "OpenAIProtocolProvider",
    "HuggingFaceProvider",
    "HFLocalProvider",
    "MockProvider",
    "build_provider",
]


def build_provider(settings: Settings) -> BaseProvider:
    """Pick the provider the current settings describe.

    huggingface + hf_mode=local  → model di `models/` dijalankan transformers
    huggingface + hf_mode=server → URL OpenAI-compatible (vLLM/llama.cpp/…)
    openai                       → OpenAI API atau gateway OpenAI-compatible
    mock                         → demo offline tanpa network
    """
    if settings.provider == "openai":
        return OpenAIProtocolProvider(
            base_url=settings.openai_base_url,
            api_key=settings.openai_api_key,
            model=settings.openai_model,
        )
    if settings.provider == "mock":
        return MockProvider()
    if (settings.hf_mode or "local") == "server":
        return HuggingFaceProvider(settings)
    return HFLocalProvider(settings)
