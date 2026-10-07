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


class CustomHttpAdapter:
    def __init__(self, config: AdapterConfig, client: httpx.AsyncClient | None = None) -> None:
        self.config = config
        self._client = client

    async def _request(self, method: str, url: str, payload: dict[str, Any] | None = None) -> httpx.Response:
        timeout = httpx.Timeout(self.config.timeout_seconds)
        headers = {"Content-Type": "application/json", **self.config.headers}
        if self._client is not None:
            return await self._client.request(method, url, json=payload, headers=headers, timeout=timeout)
        async with httpx.AsyncClient(timeout=timeout) as client:
            return await client.request(method, url, json=payload, headers=headers)

    async def generate(self, request: GenerateRequest) -> GenerateResponse:
        payload = {
            "model": self.config.model_name,
            "prompt": request.prompt,
            "system_prompt": request.system_prompt,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            **request.extra,
        }
        started = time.perf_counter()
        try:
            response = await self._request("POST", self.config.base_url, payload)
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise AdapterError(f"custom http timeout: {exc}") from exc
        except httpx.HTTPError as exc:
            raise AdapterError(f"custom http request failed: {exc}") from exc

        data = response.json()
        latency_ms = int((time.perf_counter() - started) * 1000)
        text = data.get("text") or data.get("response") or data.get("output")
        if not isinstance(text, str):
            raise AdapterError(f"invalid custom http response: {data}")
        usage = data.get("usage") or {}
        return GenerateResponse(
            text=text,
            latency_ms=latency_ms,
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            raw=data,
        )

    async def health_check(self) -> HealthStatus:
        started = time.perf_counter()
        health_path = self.config.extra.get("health_path", "/health")
        url = f"{self.config.base_url.rstrip('/')}/{str(health_path).lstrip('/')}"
        try:
            response = await self._request("GET", url)
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
