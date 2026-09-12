"""Runtime configuration (env-driven, prefix ASK_).

A mutable singleton is exposed so the UI / run.py can switch provider at runtime.
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ASK_", extra="ignore")

    # ---- LLM provider selection: "huggingface" | "openai" | "mock" ----
    provider: str = "huggingface"

    # ---- HuggingFace local (llama.cpp / any OpenAI-compatible local server) ----
    hf_base_url: str = "http://127.0.0.1:8081/v1"
    hf_model: str = "Qwen/Qwen3-8B-GGUF"
    hf_api_key: str = ""

    # ---- OpenAI (or any OpenAI-compatible remote API) ----
    openai_base_url: str = "https://api.openai.com/v1"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # ---- generation ----
    temperature: float = 0.7
    max_tokens: int = 2048
    max_steps: int = 6
    logprobs: bool = True          # mechanistic interpreter: token probabilities
    top_logprobs: int = 4

    # ---- browsing tools ----
    search_backend: str = "ddg"    # ddg | serper | tavily
    serper_api_key: str = ""
    tavily_api_key: str = ""
    fetch_timeout: float = 15.0
    user_agent: str = (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36 AskAnythingAgent/0.1"
    )

    # ---- storage ----
    db_path: str = "data/ask_anything.db"

    def active_model_label(self) -> str:
        if self.provider == "openai":
            return self.openai_model
        if self.provider == "mock":
            return "mock-agent (offline demo)"
        return self.hf_model

    def as_public_dict(self) -> dict:
        return {
            "provider": self.provider,
            "model": self.active_model_label(),
            "hf_base_url": self.hf_base_url,
            "hf_model": self.hf_model,
            "openai_base_url": self.openai_base_url,
            "openai_model": self.openai_model,
            "temperature": self.temperature,
            "max_steps": self.max_steps,
            "logprobs": self.logprobs,
            "search_backend": self.search_backend,
            "has_openai_key": bool(self.openai_api_key),
        }


settings = Settings()


def update_settings(**overrides: str | float | int | bool) -> dict:
    """Update the live settings singleton (runtime provider switch)."""
    allowed = set(Settings.model_fields.keys())
    applied = {}
    for key, value in overrides.items():
        if key not in allowed or value is None:
            continue
        setattr(settings, key, value)
        applied[key] = value
    return settings.as_public_dict()
