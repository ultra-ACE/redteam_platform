import asyncio

import httpx

from app.adapters.base import AdapterConfig, GenerateRequest
from app.adapters.mock import MockAdapter
from app.adapters.openai_compatible import OpenAICompatibleAdapter


def test_mock_adapter_generate_and_health() -> None:
    adapter = MockAdapter(model_name="mock-model")
    response = asyncio.run(adapter.generate(GenerateRequest(prompt="hello world")))
    assert "hello world" in response.text
    assert response.prompt_tokens is not None
    assert asyncio.run(adapter.health_check()).healthy


def test_openai_compatible_adapter_generate_and_health() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/chat/completions"):
            return httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": "safe response"}}],
                    "usage": {"prompt_tokens": 3, "completion_tokens": 4},
                },
            )
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": []})
        return httpx.Response(404)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = OpenAICompatibleAdapter(
        AdapterConfig(base_url="http://test.local/v1", model_name="test-model"),
        client=client,
    )

    response = asyncio.run(adapter.generate(GenerateRequest(prompt="hello")))
    assert response.text == "safe response"
    assert response.prompt_tokens == 3
    assert response.completion_tokens == 4
    assert asyncio.run(adapter.health_check()).healthy
    asyncio.run(client.aclose())
