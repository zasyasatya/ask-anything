"""Runtime configuration (env-driven, prefix ASK_).

A mutable singleton is exposed so the UI / run.py can switch provider at runtime.
"""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Base-URL fields that are canonicalised on write (users paste full endpoints).
_URL_FIELDS = ("hf_base_url", "openai_base_url")

#: `hf_mode` values: how the `huggingface` provider reaches a model.
HF_MODES = ("local", "server")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ASK_",
        extra="ignore",
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
    )

    # ---- LLM provider selection: "huggingface" | "openai" | "mock" ----
    provider: str = "huggingface"

    # ---- HuggingFace: model lokal (in-process transformers) ----
    # local  = model di folder `models/` dijalankan langsung oleh proses ini
    # server = URL OpenAI-compatible (vLLM / llama.cpp / LM Studio / gateway)
    hf_mode: str = "local"
    #: repo id model offline yang aktif, mis. "Qwen/Qwen3-1.7B"
    hf_model: str = ""
    hf_base_url: str = "http://127.0.0.1:8081/v1"   # hanya untuk hf_mode=server
    hf_api_key: str = ""                            # hanya untuk hf_mode=server
    thinking: bool = True          # enable_thinking / <think> reasoning

    # ---- offline models: HuggingFace Hub → folder `models/` di project ----
    models_dir: str = "models"     # project folder that holds downloaded models
    hf_endpoint: str = "https://huggingface.co"   # mirror: hf-mirror.com etc.
    hf_token: str = ""             # token Hub utk repo privat/gated (hf_…)

    # ---- local inference tuning ----
    hf_device: str = ""            # "" = auto (cuda → mps → cpu)
    hf_dtype: str = "auto"         # auto | float16 | bfloat16 | float32
    hf_threads: int = 0            # 0 = biar torch yang memilih
    hf_trust_remote_code: bool = False  # repo dengan kode kustom (DeepSeek dsb.)

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
    #: Endpoint pencarian gaya DuckDuckGo-lite. Bisa diarahkan ke gateway
    #: pencarian internal/self-host (atau server demo offline untuk pengujian
    #: end-to-end UI) tanpa mengubah kode tool — parameter & respons harus
    #: sama dengan /lite/ (link <a href="http…"> + sel snippet di sebelahnya).
    search_ddg_url: str = "https://lite.duckduckgo.com/lite/"
    serper_api_key: str = ""
    tavily_api_key: str = ""
    fetch_timeout: float = 15.0
    user_agent: str = (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36 AskAnythingAgent/0.1"
    )

    # ---- deep research ----
    deep_research_max_queries: int = 6
    deep_research_max_results_per_query: int = 8

    # ---- governance (halaman Admin) ----
    #: Bila diset, semua endpoint /api/admin/* mewajibkan header X-Admin-Token.
    admin_token: str = ""
    artifacts_dir: str = "data/artifacts"   # penyimpanan artifact (gambar/pptx)
    rag_dir: str = "data/rag"               # arsip PDF mentah mode RAG

    # ---- storage ----
    db_path: str = "data/ask_anything.db"

    def active_model_label(self) -> str:
        if self.provider == "openai":
            return self.openai_model
        if self.provider == "mock":
            return "mock-agent (offline demo)"
        if self.hf_mode == "server":
            return f"{self.hf_model or self.hf_base_url} (server)"
        return self.hf_model or "(belum ada model offline)"

    def resolved_models_dir(self) -> Path:
        """Absolute path of the folder that stores downloaded models."""
        p = Path(self.models_dir).expanduser()
        if not p.is_absolute():
            p = PROJECT_ROOT / p
        return p

    def as_public_dict(self) -> dict:
        return {
            "provider": self.provider,
            "model": self.active_model_label(),
            "hf_mode": self.hf_mode,
            "hf_base_url": self.hf_base_url,
            "hf_model": self.hf_model,
            "thinking": self.thinking,
            "models_dir": str(self.resolved_models_dir()),
            "hf_endpoint": self.hf_endpoint,
            "hf_device": self.hf_device,
            "hf_dtype": self.hf_dtype,
            "openai_base_url": self.openai_base_url,
            "openai_model": self.openai_model,
            "temperature": self.temperature,
            "max_steps": self.max_steps,
            "logprobs": self.logprobs,
            "search_backend": self.search_backend,
            "search_ddg_url": self.search_ddg_url,
            "has_openai_key": bool(self.openai_api_key),
            "has_hf_key": bool(self.hf_api_key),
            "has_hf_token": bool(self.hf_token),
            # masked so the UI can show "tersimpan" without exposing the key
            "hf_api_key_masked": _mask(self.hf_api_key),
            "hf_token_masked": _mask(self.hf_token),
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
    if applied.get("hf_mode") not in (None, *HF_MODES):
        settings.hf_mode = "local"
        applied["hf_mode"] = settings.hf_mode
    if any(field in applied for field in _URL_FIELDS):
        _normalize_urls(applied)
    return settings.as_public_dict()
