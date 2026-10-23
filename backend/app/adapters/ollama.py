import time
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx

from app.adapters.base import (
    AdapterConfig,
    AdapterError,
    GenerateRequest,
    GenerateResponse,
    HealthStatus,
)

# 用户经常会直接粘贴文档里的完整端点（/api/generate、/api/tags）或
# OpenAI-compatible 的 /v1 地址。Ollama 原生接口的根地址应该只保留
# scheme + host + 可选前缀，因此这里统一把已知后缀去掉，避免出现
# /v1/api/generate、/api/api/generate 这类拼接错误导致的 404。
_BASE_URL_SUFFIXES = (
    "/api/generate",
    "/api/chat",
    "/api/tags",
    "/api/show",
    "/api/embeddings",
    "/api/ps",
    "/api/version",
    "/api",
    "/v1/chat/completions",
    "/v1/completions",
    "/v1/models",
    "/v1",
)

# 允许透传给 Ollama options 的通用采样参数。
_OLLAMA_OPTION_KEYS = (
    "num_ctx",
    "top_p",
    "top_k",
    "repeat_penalty",
    "presence_penalty",
    "frequency_penalty",
    "seed",
    "stop",
)


def normalize_ollama_base_url(raw: str | None) -> str:
    """把用户填写的服务地址收敛为 Ollama 原生 API 的根地址。

    例：
    - ``http://host:11434/v1`` -> ``http://host:11434``
    - ``http://host:11434/api`` -> ``http://host:11434``
    - ``http://host:11434/api/generate`` -> ``http://host:11434``
    - ``http://gateway/ollama/api`` -> ``http://gateway/ollama``
    """
    text = (raw or "").strip()
    if not text:
        return ""
    if "://" not in text:
        text = f"http://{text}"

    parts = urlsplit(text)
    path = parts.path.rstrip("/")
    lowered_path = path.lower()
    for suffix in _BASE_URL_SUFFIXES:
        if lowered_path.endswith(suffix):
            path = path[: -len(suffix)].rstrip("/")
            break
    return urlunsplit((parts.scheme, parts.netloc, path, "", ""))


class OllamaAdapter:
    def __init__(self, config: AdapterConfig, client: httpx.AsyncClient | None = None) -> None:
        self.config = config
        self._client = client
        self._base_url = normalize_ollama_base_url(config.base_url)

    async def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> httpx.Response:
        if not self._base_url:
            raise AdapterError("ollama base_url 不能为空")
        url = f"{self._base_url}/{path.lstrip('/')}"
        timeout = httpx.Timeout(self.config.timeout_seconds)
        headers = {"Content-Type": "application/json", **self.config.headers}
        if self._client is not None:
            return await self._client.request(method, url, json=payload, headers=headers, timeout=timeout)
        async with httpx.AsyncClient(timeout=timeout) as client:
            return await client.request(method, url, json=payload, headers=headers)

    @staticmethod
    def _response_detail(response: httpx.Response) -> str:
        """优先返回 Ollama 的 ``{"error": "..."}``，而不是只报一个裸 404。"""
        try:
            data = response.json()
        except ValueError:
            return (response.text or "").strip()[:500]
        if isinstance(data, dict):
            for key in ("error", "message", "detail"):
                value = data.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()[:500]
        return str(data)[:500]

    def _http_error(self, method: str, response: httpx.Response) -> str:
        detail = self._response_detail(response)
        request_url = str(response.request.url) if response.request is not None else self._base_url
        message = (
            f"ollama request failed: HTTP {response.status_code} "
            f"{response.reason_phrase} {method} {request_url}"
        )
        if detail:
            message = f"{message}：{detail}"
        return message

    async def _list_models(self) -> list[str]:
        response = await self._request("GET", "/api/tags")
        if response.status_code >= 400:
            raise AdapterError(self._http_error("GET", response))
        try:
            data = response.json()
        except ValueError as exc:
            raise AdapterError(f"invalid ollama tags response: {response.text[:500]}") from exc
        models = data.get("models") if isinstance(data, dict) else None
        if not isinstance(models, list):
            raise AdapterError(f"invalid ollama tags response: {data}")
        names: list[str] = []
        for item in models:
            if not isinstance(item, dict):
                continue
            name = item.get("name") or item.get("model")
            if isinstance(name, str) and name:
                names.append(name)
        return names

    @staticmethod
    def _match_model_name(configured: str, available: list[str]) -> str | None:
        """兼容大小写和省略 ``:latest`` 的写法，返回实际存在的模型名。"""
        target = configured.strip()
        if not target:
            return None
        if target in available:
            return target

        lowered = {name.lower(): name for name in available}
        if target.lower() in lowered:
            return lowered[target.lower()]

        def without_latest(name: str) -> str:
            return name[:-7] if name.lower().endswith(":latest") else name

        target_key = without_latest(target).lower()
        matches = [name for name in available if without_latest(name).lower() == target_key]
        if len(matches) == 1:
            return matches[0]
        return None

    async def _resolve_model_name(self) -> str:
        """在真正生成前确认模型已安装，并把 404 变成可执行的提示。"""
        configured = (self.config.model_name or "").strip()
        if not configured:
            raise AdapterError("ollama model_name 不能为空")

        try:
            available = await self._list_models()
        except (AdapterError, httpx.HTTPError):
            # /api/tags 不可用（例如网关只开放了 /api/generate）时不要阻断生成，
            # 继续请求 /api/generate，让它返回真实错误。
            return configured

        if not available:
            raise AdapterError(
                "ollama 服务已连接，但本地没有已安装的模型。请先执行 ollama pull <model>。"
            )

        resolved = self._match_model_name(configured, available)
        if resolved is None:
            preview = "、".join(available[:10])
            raise AdapterError(
                f"ollama 模型 {configured!r} 未安装；本地可用模型：{preview}。"
                f"请先执行 ollama pull {configured}，或把模型标识改成上面的名称。"
            )
        return resolved

    def _build_payload(self, request: GenerateRequest, model_name: str) -> dict[str, Any]:
        prompt = request.prompt
        if request.system_prompt:
            prompt = f"{request.system_prompt}\n\n{prompt}"

        options: dict[str, Any] = {
            "temperature": request.temperature,
            "num_predict": request.max_tokens,
        }
        extra = {**(self.config.extra or {}), **(request.extra or {})}
        for key in _OLLAMA_OPTION_KEYS:
            if key in extra and extra[key] is not None:
                options[key] = extra[key]

        payload: dict[str, Any] = {
            "model": model_name,
            "prompt": prompt,
            "stream": False,
            "options": options,
        }
        keep_alive = extra.get("keep_alive")
        if keep_alive is not None:
            payload["keep_alive"] = keep_alive
        return payload

    async def generate(self, request: GenerateRequest) -> GenerateResponse:
        started = time.perf_counter()
        try:
            model_name = await self._resolve_model_name()
            payload = self._build_payload(request, model_name)
            response = await self._request("POST", "/api/generate", payload)
        except httpx.TimeoutException as exc:
            raise AdapterError(
                f"ollama timeout after {self.config.timeout_seconds}s"
                f"（model={self.config.model_name}）。首次加载大模型或 CPU 推理可能超过该时间，"
                "请调大任务的“单次超时”，或在模型 default_params 中设置 timeout_seconds。"
            ) from exc
        except httpx.HTTPError as exc:
            raise AdapterError(f"ollama request failed: {exc}") from exc

        if response.status_code >= 400:
            raise AdapterError(self._http_error("POST", response))

        try:
            data = response.json()
        except ValueError as exc:
            raise AdapterError(f"invalid ollama response: {response.text[:500]}") from exc
        if not isinstance(data, dict):
            raise AdapterError(f"invalid ollama response: {data}")

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
        """连接测试同时校验“服务可达”和“配置的模型已安装”。

        只请求 /api/tags 会让模型名写错时也显示连接正常，任务执行时才 404。
        """
        started = time.perf_counter()

        def elapsed() -> int:
            return int((time.perf_counter() - started) * 1000)

        try:
            available = await self._list_models()
        except httpx.TimeoutException:
            return HealthStatus(
                status="unhealthy",
                latency_ms=elapsed(),
                error_message=(
                    f"ollama timeout after {self.config.timeout_seconds}s：服务未在超时时间内响应"
                ),
            )
        except AdapterError as exc:
            return HealthStatus(status="unhealthy", latency_ms=elapsed(), error_message=str(exc))
        except httpx.HTTPError as exc:
            return HealthStatus(
                status="unhealthy",
                latency_ms=elapsed(),
                error_message=f"ollama request failed: {exc}",
            )

        configured = (self.config.model_name or "").strip()
        if not configured:
            return HealthStatus(
                status="unhealthy",
                latency_ms=elapsed(),
                error_message="ollama 服务可访问，但模型标识 model_name 为空",
            )
        if not available:
            return HealthStatus(
                status="unhealthy",
                latency_ms=elapsed(),
                error_message=(
                    "ollama 服务可访问，但本地没有已安装的模型。请先执行 ollama pull <model>。"
                ),
            )
        if self._match_model_name(configured, available) is None:
            preview = "、".join(available[:10])
            return HealthStatus(
                status="unhealthy",
                latency_ms=elapsed(),
                error_message=(
                    f"ollama 服务可访问，但模型 {configured!r} 未安装；"
                    f"本地可用模型：{preview}。"
                ),
            )
        return HealthStatus(status="healthy", latency_ms=elapsed())
