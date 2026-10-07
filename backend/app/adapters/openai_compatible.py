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


class OpenAICompatibleAdapter:
    def __init__(self, config: AdapterConfig, client: httpx.AsyncClient | None = None) -> None:
        self.config = config
        self._client = client

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        headers.update(self.config.headers)
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        return headers

    async def _post(self, path: str, payload: dict[str, Any]) -> httpx.Response:
        url = f"{self.config.base_url.rstrip('/')}/{path.lstrip('/')}"
        timeout = httpx.Timeout(self.config.timeout_seconds)
        if self._client is not None:
            return await self._client.post(url, json=payload, headers=self._headers(), timeout=timeout)
        async with httpx.AsyncClient(timeout=timeout) as client:
            return await client.post(url, json=payload, headers=self._headers())

    async def _get(self, path: str) -> httpx.Response:
        url = f"{self.config.base_url.rstrip('/')}/{path.lstrip('/')}"
        timeout = httpx.Timeout(self.config.timeout_seconds)
        if self._client is not None:
            return await self._client.get(url, headers=self._headers(), timeout=timeout)
        async with httpx.AsyncClient(timeout=timeout) as client:
            return await client.get(url, headers=self._headers())

    async def generate(self, request: GenerateRequest) -> GenerateResponse:
        messages: list[dict[str, str]] = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.prompt})

        payload = {
            "model": self.config.model_name,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            **request.extra,
        }
        started = time.perf_counter()
        try:
            response = await self._post("/chat/completions", payload)
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise AdapterError(f"model timeout: {exc}") from exc
        except httpx.HTTPError as exc:
            raise AdapterError(f"model request failed: {exc}") from exc

        data = response.json()
        latency_ms = int((time.perf_counter() - started) * 1000)
        try:
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AdapterError(f"invalid openai-compatible response: {data}") from exc

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
        try:
            response = await self._get("/models")
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
