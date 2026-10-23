import os

from app.adapters.base import AdapterConfig, AdapterError, ModelAdapter
from app.adapters.custom_http import CustomHttpAdapter
from app.adapters.mock import MockAdapter
from app.adapters.ollama import OllamaAdapter
from app.adapters.openai_compatible import OpenAICompatibleAdapter
from app.core.config import settings
from app.db.models import ModelRegistry


def resolve_secret_ref(secret_ref: str | None) -> str | None:
    if not secret_ref:
        return None
    text = secret_ref.strip()
    if not text:
        return None
    if text.startswith("env:"):
        return os.getenv(text.removeprefix("env:"))
    if text.startswith("literal:"):
        return text.removeprefix("literal:")
    # 历史数据里可能直接存了明文密钥，按 literal 处理，避免静默丢鉴权
    return text


def _resolve_timeout(model: ModelRegistry, override: int | None) -> int:
    params = model.default_params or {}
    for value in (override, params.get("timeout_seconds")):
        try:
            parsed = int(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
        if parsed > 0:
            return parsed
    return settings.default_model_timeout_seconds


def build_adapter(model: ModelRegistry, *, timeout_seconds: int | None = None) -> ModelAdapter:
    adapter_type = model.adapter_type
    config = AdapterConfig(
        base_url=model.base_url or "",
        model_name=model.model_name,
        api_key=resolve_secret_ref(model.secret_ref),
        timeout_seconds=_resolve_timeout(model, timeout_seconds),
        extra=model.default_params or {},
    )

    if adapter_type == "openai_compatible":
        return OpenAICompatibleAdapter(config)
    if adapter_type == "ollama":
        return OllamaAdapter(config)
    if adapter_type == "custom_http":
        return CustomHttpAdapter(config)
    if adapter_type == "mock":
        return MockAdapter(model_name=model.model_name)

    raise AdapterError(f"unsupported adapter_type: {adapter_type}")
