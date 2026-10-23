import asyncio
from types import SimpleNamespace

import httpx
import pytest

from app.adapters.base import AdapterConfig, AdapterError, GenerateRequest
from app.adapters.factory import build_adapter
from app.adapters.ollama import OllamaAdapter, normalize_ollama_base_url


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_normalize_ollama_base_url_accepts_pasted_endpoints() -> None:
    assert normalize_ollama_base_url("http://host:11434") == "http://host:11434"
    assert normalize_ollama_base_url("http://host:11434/") == "http://host:11434"
    assert normalize_ollama_base_url("http://host:11434/v1") == "http://host:11434"
    assert normalize_ollama_base_url("http://host:11434/api") == "http://host:11434"
    assert (
        normalize_ollama_base_url("http://host:11434/api/generate")
        == "http://host:11434"
    )
    assert (
        normalize_ollama_base_url("http://host:11434/v1/chat/completions")
        == "http://host:11434"
    )
    assert normalize_ollama_base_url("host:11434") == "http://host:11434"
    assert (
        normalize_ollama_base_url("http://gateway/ollama/api/")
        == "http://gateway/ollama"
    )


def test_generate_uses_normalized_root_api_path() -> None:
    seen_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_paths.append(request.url.path)
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "qwen2.5:7b"}]})
        if request.url.path == "/api/generate":
            return httpx.Response(
                200,
                json={
                    "response": "decoded answer",
                    "prompt_eval_count": 12,
                    "eval_count": 5,
                },
            )
        return httpx.Response(404, json={"error": "not found"})

    client = _client(handler)
    adapter = OllamaAdapter(
        AdapterConfig(base_url="http://test.local/v1", model_name="qwen2.5:7b"),
        client=client,
    )

    response = asyncio.run(adapter.generate(GenerateRequest(prompt="hello")))

    assert response.text == "decoded answer"
    assert response.prompt_tokens == 12
    assert response.completion_tokens == 5
    assert "/api/tags" in seen_paths
    assert "/api/generate" in seen_paths
    assert "/v1/api/generate" not in seen_paths
    asyncio.run(client.aclose())


def test_generate_reports_ollama_404_body_instead_of_bare_client_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            # 模拟只开放 /api/generate 的网关：tags 不可用时不阻断生成
            return httpx.Response(500, json={"error": "tags disabled"})
        return httpx.Response(
            404,
            json={"error": "model 'qwen2.5:7b' not found, try pulling it first"},
        )

    client = _client(handler)
    adapter = OllamaAdapter(
        AdapterConfig(base_url="http://test.local", model_name="qwen2.5:7b"),
        client=client,
    )

    with pytest.raises(AdapterError) as exc_info:
        asyncio.run(adapter.generate(GenerateRequest(prompt="hello")))

    message = str(exc_info.value)
    assert "HTTP 404" in message
    assert "model 'qwen2.5:7b' not found" in message
    asyncio.run(client.aclose())


def test_generate_fails_fast_when_model_is_not_installed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/tags"
        return httpx.Response(
            200,
            json={
                "models": [
                    {"name": "qwen2.5:7b"},
                    {"name": "llama3.1:8b"},
                ]
            },
        )

    client = _client(handler)
    adapter = OllamaAdapter(
        AdapterConfig(base_url="http://test.local", model_name="missing:1b"),
        client=client,
    )

    with pytest.raises(AdapterError) as exc_info:
        asyncio.run(adapter.generate(GenerateRequest(prompt="hello")))

    message = str(exc_info.value)
    assert "未安装" in message
    assert "qwen2.5:7b" in message
    assert "llama3.1:8b" in message
    asyncio.run(client.aclose())


def test_health_check_verifies_model_is_installed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/tags"
        return httpx.Response(200, json={"models": [{"name": "qwen2.5:7b"}]})

    client = _client(handler)
    healthy = OllamaAdapter(
        AdapterConfig(base_url="http://test.local/v1", model_name="qwen2.5:7b"),
        client=client,
    )
    status = asyncio.run(healthy.health_check())
    assert status.healthy
    asyncio.run(client.aclose())

    client = _client(handler)
    missing = OllamaAdapter(
        AdapterConfig(base_url="http://test.local", model_name="missing:1b"),
        client=client,
    )
    status = asyncio.run(missing.health_check())
    assert not status.healthy
    assert "未安装" in (status.error_message or "")
    assert "qwen2.5:7b" in (status.error_message or "")
    asyncio.run(client.aclose())


def test_health_check_accepts_omitted_latest_tag() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"models": [{"name": "qwen2.5:latest"}]})

    client = _client(handler)
    adapter = OllamaAdapter(
        AdapterConfig(base_url="http://test.local", model_name="qwen2.5"),
        client=client,
    )
    assert asyncio.run(adapter.health_check()).healthy
    asyncio.run(client.aclose())


def test_generate_timeout_message_mentions_timeout_and_model() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "qwen2.5:7b"}]})
        raise httpx.ReadTimeout("read timed out", request=request)

    client = _client(handler)
    adapter = OllamaAdapter(
        AdapterConfig(
            base_url="http://test.local",
            model_name="qwen2.5:7b",
            timeout_seconds=300,
        ),
        client=client,
    )

    with pytest.raises(AdapterError) as exc_info:
        asyncio.run(adapter.generate(GenerateRequest(prompt="hello")))

    message = str(exc_info.value)
    assert "timeout after 300s" in message
    assert "qwen2.5:7b" in message
    asyncio.run(client.aclose())


def test_build_adapter_honours_task_and_model_timeout() -> None:
    model = SimpleNamespace(
        adapter_type="ollama",
        base_url="http://127.0.0.1:11434",
        model_name="qwen2.5:7b",
        secret_ref=None,
        default_params={"timeout_seconds": 180},
    )
    assert build_adapter(model).config.timeout_seconds == 180
    assert build_adapter(model, timeout_seconds=600).config.timeout_seconds == 600
    assert (
        build_adapter(
            SimpleNamespace(**{**model.__dict__, "default_params": {}})
        ).config.timeout_seconds
        == 600
    )
