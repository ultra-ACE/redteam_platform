import time
from typing import Any

import httpx

from app.adapters.base import (
    AdapterConfig,
    AdapterError,
    GenerateRequest,
    GenerateResponse,
    HealthStatus,
)


class OllamaAdapter:
    def __init__(self, config: AdapterConfig, client: httpx.AsyncClient | None = None) -> None:
        self.config = config
        self._client = client

    async def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> httpx.Response:
        url = f"{self.config.base_url.rstrip('/')}/{path.lstrip('/')}"
        timeout = httpx.Timeout(self.config.timeout_seconds)
        headers = {"Content-Type": "application/json", **self.config.headers}
        if self._client is not None:
            return await self._client.request(method, url, json=payload, headers=headers, timeout=timeout)
        async with httpx.AsyncClient(timeout=timeout) as client:
            return await client.request(method, url, json=payload, headers=headers)

    async def generate(self, request: GenerateRequest) -> GenerateResponse:
        prompt = request.prompt
        if request.system_prompt:
            prompt = f"{request.system_prompt}\n\n{prompt}"
        payload = {
            "model": self.config.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_tokens,
            },
        }
        started = time.perf_counter()
        try:
            response = await self._request("POST", "/api/generate", payload)
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise AdapterError(f"ollama timeout: {exc}") from exc
        except httpx.HTTPError as exc:
            raise AdapterError(f"ollama request failed: {exc}") from exc

        data = response.json()
        latency_ms = int((time.perf_counter() - started) * 1000)
        text = data.get("response")
        if not isinstance(text, str):
            raise AdapterError(f"invalid ollama response: {data}")
        return GenerateResponse(
            text=text,
            latency_ms=latency_ms,
            prompt_tokens=data.get("prompt_eval_count"),
            completion_tokens=data.get("eval_count"),
            raw=data,
        )

    async def health_check(self) -> HealthStatus:
        started = time.perf_counter()
        try:
            response = await self._request("GET", "/api/tags")
            response.raise_for_status()
        except Exception as exc:
            return HealthStatus(
                status="unhealthy",
                latency_ms=int((time.perf_counter() - started) * 1000),
                error_message=str(exc),
            )
        return HealthStatus(
            status="healthy",
            latency_ms=int((time.perf_counter() - started) * 1000),
        )
