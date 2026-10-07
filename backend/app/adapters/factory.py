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
    if secret_ref.startswith("env:"):
        return os.getenv(secret_ref.removeprefix("env:"))
    if secret_ref.startswith("literal:"):
        return secret_ref.removeprefix("literal:")
    return None


def build_adapter(model: ModelRegistry) -> ModelAdapter:
    adapter_type = model.adapter_type
    config = AdapterConfig(
        base_url=model.base_url or "",
        model_name=model.model_name,
        api_key=resolve_secret_ref(model.secret_ref),
        timeout_seconds=settings.default_model_timeout_seconds,
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
