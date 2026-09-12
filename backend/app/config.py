"""Runtime configuration (env-driven, prefix ASK_).

A mutable singleton is exposed so the UI / run.py can switch provider at runtime.
"""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Base-URL fields that are canonicalised on write (users paste full endpoints).
_URL_FIELDS = ("hf_base_url", "openai_base_url")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ASK_", extra="ignore")

    # ---- LLM provider selection: "huggingface" | "openai" | "mock" ----
    provider: str = "huggingface"

    # ---- HuggingFace local (llama.cpp / any OpenAI-compatible local server) ----
    # Any OpenAI-compatible base URL works: a bare host, "…/v1", or a full
    # endpoint such as "https://ai.sumopod.com/v1/chat/completions".
    hf_base_url: str = "http://127.0.0.1:8081/v1"
    hf_model: str = "Qwen/Qwen3-8B-GGUF"
    hf_api_key: str = ""
    thinking: bool = True          # chat_template_kwargs.enable_thinking

    # ---- offline models: GGUF catalog + local llama.cpp runtime ----
    models_dir: str = "models"     # project folder that holds downloaded GGUFs
    hf_endpoint: str = "https://huggingface.co"   # mirror: hf-mirror.com etc.
    llama_server_bin: str = ""     # override `llama-server` discovery
    llama_extra_args: str = ""     # e.g. "--reasoning-format auto"
    hf_port: int = 8081
    hf_ctx_size: int = 4096
    hf_gpu_layers: int = -1        # -1 = CPU only, 99 = offload everything

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

    def resolved_models_dir(self) -> Path:
        """Absolute path of the folder that stores downloaded GGUF models."""
        p = Path(self.models_dir).expanduser()
        if not p.is_absolute():
            p = PROJECT_ROOT / p
        return p

    def as_public_dict(self) -> dict:
        return {
            "provider": self.provider,
            "model": self.active_model_label(),
            "hf_base_url": self.hf_base_url,
            "hf_model": self.hf_model,
            "thinking": self.thinking,
            "models_dir": str(self.resolved_models_dir()),
            "hf_port": self.hf_port,
            "hf_ctx_size": self.hf_ctx_size,
            "openai_base_url": self.openai_base_url,
            "openai_model": self.openai_model,
            "temperature": self.temperature,
            "max_steps": self.max_steps,
            "logprobs": self.logprobs,
            "search_backend": self.search_backend,
            "has_openai_key": bool(self.openai_api_key),
            "has_hf_key": bool(self.hf_api_key),
            # masked so the UI can show "tersimpan" without exposing the key
            "hf_api_key_masked": _mask(self.hf_api_key),
            "openai_api_key_masked": _mask(self.openai_api_key),
        }


settings = Settings()


def _mask(value: str) -> str:
    if not value:
        return ""
    return f"{value[:3]}…{value[-4:]}" if len(value) > 8 else "…" * len(value)


def _normalize_urls(applied: dict) -> dict:
    """Canonicalise pasted base URLs (import is local: providers import config)."""
    from .providers.url_utils import normalize_openai_base_url

    for field in _URL_FIELDS:
        value = getattr(settings, field, "")
        if not value:
            continue
        canonical = normalize_openai_base_url(value)
        if canonical and canonical != value:
            setattr(settings, field, canonical)
        applied[field] = getattr(settings, field)
    return applied


def update_settings(**overrides: str | float | int | bool) -> dict:
    """Update the live settings singleton (runtime provider switch)."""
    allowed = set(Settings.model_fields.keys())
    applied = {}
    for key, value in overrides.items():
        if key not in allowed or value is None:
            continue
        # Keys are special: the field is *absent* (None) when the user did not
        # touch it, and an explicit "" when they cleared it. Only absent keys
        # are ignored, so a wrong/expired key can actually be removed.
        setattr(settings, key, value)
        applied[key] = value
    if any(field in applied for field in _URL_FIELDS):
        _normalize_urls(applied)
    return settings.as_public_dict()
