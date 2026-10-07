import asyncio
import time

from app.adapters.base import GenerateRequest, GenerateResponse, HealthStatus


class MockAdapter:
    def __init__(self, model_name: str = "mock-model", delay_seconds: float = 0.0) -> None:
        self.model_name = model_name
        self.delay_seconds = delay_seconds

    async def generate(self, request: GenerateRequest) -> GenerateResponse:
        started = time.perf_counter()
        if self.delay_seconds:
            await asyncio.sleep(self.delay_seconds)
        text = f"[mock:{self.model_name}] {request.prompt[:120]}"
        return GenerateResponse(
            text=text,
            latency_ms=int((time.perf_counter() - started) * 1000),
            prompt_tokens=max(1, len(request.prompt) // 4),
            completion_tokens=max(1, len(text) // 4),
            raw={"mock": True, "model": self.model_name},
        )

    async def health_check(self) -> HealthStatus:
        started = time.perf_counter()
        if self.delay_seconds:
            await asyncio.sleep(self.delay_seconds)
        return HealthStatus(status="healthy", latency_ms=int((time.perf_counter() - started) * 1000))
