from ..config import Settings
from .base import BaseProvider, StreamEvent, ToolCall
from .huggingface_provider import HuggingFaceProvider
from .mock_provider import MockProvider
from .openai_provider import OpenAIProtocolProvider

__all__ = [
    "BaseProvider",
    "StreamEvent",
    "ToolCall",
    "OpenAIProtocolProvider",
    "HuggingFaceProvider",
    "MockProvider",
    "build_provider",
]


def build_provider(settings: Settings) -> BaseProvider:
    if settings.provider == "openai":
        return OpenAIProtocolProvider(
            base_url=settings.openai_base_url,
            api_key=settings.openai_api_key,
            model=settings.openai_model,
        )
    if settings.provider == "mock":
        return MockProvider()
    return HuggingFaceProvider(settings)
