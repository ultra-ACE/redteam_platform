from dataclasses import dataclass, field
from typing import Any, Protocol


class AdapterError(Exception):
    """Base error raised by model adapters."""


@dataclass
class AdapterConfig:
    base_url: str
    model_name: str
    api_key: str | None = None
    timeout_seconds: int = 120
    headers: dict[str, str] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class GenerateRequest:
    prompt: str
    system_prompt: str | None = None
    temperature: float = 0.2
    max_tokens: int = 1024
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class GenerateResponse:
    text: str
    latency_ms: int
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    raw: dict[str, Any] | None = None


@dataclass
class HealthStatus:
    status: str
    latency_ms: int | None = None
    error_message: str | None = None

    @property
    def healthy(self) -> bool:
        return self.status == "healthy"


class ModelAdapter(Protocol):
    async def generate(self, request: GenerateRequest) -> GenerateResponse:
        ...

    async def health_check(self) -> HealthStatus:
        ...
