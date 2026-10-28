from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
import pytest
from backend.config import Settings
from backend.providers import (
    GeminiProvider,
    GenerationRequest,
    GroqProvider,
    MiniMaxProvider,
    MockProvider,
    ProviderError,
    RetryPolicy,
    TokenUsage,
    create_configured_providers,
)
from backend.providers.factory import create_custom_provider


def _client(handler: Any) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def _no_sleep(delay: float) -> None:
    return None


def test_gemini_adapter_builds_request_and_normalizes_usage() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["headers"] = dict(request.headers)
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "responseId": "req-gemini-1",
                "modelVersion": "gemini-test-revision",
                "candidates": [
                    {
                        "content": {"parts": [{"text": "Hello"}, {"text": " there"}]},
                        "finishReason": "STOP",
                    }
                ],
                "usageMetadata": {
                    "promptTokenCount": 7,
                    "candidatesTokenCount": 3,
                    "totalTokenCount": 10,
                },
            },
        )

    async def run() -> Any:
        async with _client(handler) as client:
            provider = GeminiProvider(
                api_key="test-gemini-key",
                default_model_id="gemini-test",
                client=client,
            )
            return await provider.generate(
                GenerationRequest(
                    prompt="Say hello",
                    system_prompt="Be brief",
                    temperature=0.2,
                    max_output_tokens=20,
                )
            )

    response = asyncio.run(run())

    assert seen["url"] == (
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-test:generateContent"
    )
    assert seen["headers"]["x-goog-api-key"] == "test-gemini-key"
    assert seen["body"]["systemInstruction"]["parts"][0]["text"] == "Be brief"
    assert seen["body"]["generationConfig"] == {"temperature": 0.2, "maxOutputTokens": 20}
    assert "model" not in seen["body"]
    assert response.provider == "gemini"
    assert response.model_id == "gemini-test-revision"
    assert response.text == "Hello there"
    assert response.usage == TokenUsage(input_tokens=7, output_tokens=3, total_tokens=10)
    assert response.finish_reason == "STOP"
    assert response.request_id == "req-gemini-1"
    assert response.latency_ms >= 0


def test_retry_is_bounded_and_honors_retry_after() -> None:
    attempts = 0
    delays: list[float] = []

    async def record_sleep(delay: float) -> None:
        delays.append(delay)

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(429, headers={"Retry-After": "1"}, json={"error": "busy"})
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}]},
        )

    async def run() -> Any:
        async with _client(handler) as client:
            provider = MiniMaxProvider(
                api_key="key",
                default_model_id="minimax/model",
                client=client,
                retry_policy=RetryPolicy(
                    max_attempts=2, initial_delay_seconds=0.1, max_delay_seconds=0.5
                ),
                sleep=record_sleep,
            )
            return await provider.generate(GenerationRequest(prompt="test"))

    response = asyncio.run(run())

    assert response.text == "ok"
    assert attempts == 2
    assert delays == [0.5]


def test_authentication_errors_are_not_retried_or_expose_credentials() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(401, json={"error": {"message": "secret should not leak"}})

    async def run() -> None:
        async with _client(handler) as client:
            provider = GeminiProvider(
                api_key="sensitive-test-value",
                default_model_id="gemini-test",
                client=client,
                retry_policy=RetryPolicy(max_attempts=3),
                sleep=_no_sleep,
            )
            await provider.generate(GenerationRequest(prompt="test"))

    with pytest.raises(ProviderError) as error:
        asyncio.run(run())

    assert error.value.error_type == "authentication"
    assert error.value.status_code == 401
    assert attempts == 1
    assert "sensitive-test-value" not in str(error.value)
    assert "secret should not leak" not in str(error.value)


def test_retry_stops_after_max_attempts_and_returns_sanitized_error() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(503, json={"detail": "private upstream response"})

    async def run() -> None:
        async with _client(handler) as client:
            provider = MiniMaxProvider(
                api_key="key",
                default_model_id="minimax/model",
                client=client,
                retry_policy=RetryPolicy(
                    max_attempts=2, initial_delay_seconds=0, max_delay_seconds=0
                ),
                sleep=_no_sleep,
            )
            await provider.generate(GenerationRequest(prompt="test"))

    with pytest.raises(ProviderError, match="HTTP 503") as error:
        asyncio.run(run())

    assert error.value.retryable is True
    assert attempts == 2
    assert "private upstream response" not in str(error.value)


def test_transport_timeout_retries_once_when_policy_allows() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise httpx.ReadTimeout("simulated timeout", request=request)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "recovered"}, "finish_reason": "stop"}]},
        )

    async def run() -> Any:
        async with _client(handler) as client:
            provider = MiniMaxProvider(
                api_key="key",
                default_model_id="minimax/model",
                client=client,
                retry_policy=RetryPolicy(
                    max_attempts=2, initial_delay_seconds=0, max_delay_seconds=0
                ),
                sleep=_no_sleep,
            )
            return await provider.generate(GenerationRequest(prompt="test"))

    response = asyncio.run(run())

    assert response.text == "recovered"
    assert attempts == 2


def test_cost_estimator_is_optional_and_uses_normalized_usage() -> None:
    class FixtureEstimator:
        def __init__(self) -> None:
            self.args: tuple[str, int | None, int | None] | None = None

        def estimate_usd(
            self, model_id: str, input_tokens: int | None, output_tokens: int | None
        ) -> float:
            self.args = (model_id, input_tokens, output_tokens)
            return 0.004

    estimator = FixtureEstimator()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": "minimax/actual-model",
                "usage": {"prompt_tokens": 4, "completion_tokens": 5},
                "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
            },
        )

    async def run() -> Any:
        async with _client(handler) as client:
            provider = MiniMaxProvider(
                api_key="key",
                default_model_id="minimax/requested-model",
                client=client,
                cost_estimator=estimator,
            )
            return await provider.generate(GenerationRequest(prompt="test"))

    response = asyncio.run(run())

    assert response.estimated_cost_usd == 0.004
    assert estimator.args == ("minimax/actual-model", 4, 5)


def test_provider_normalizes_malformed_success_payload_as_provider_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": []})

    async def run() -> None:
        async with _client(handler) as client:
            provider = MiniMaxProvider(
                api_key="key", default_model_id="minimax/model", client=client
            )
            await provider.generate(GenerationRequest(prompt="test"))

    with pytest.raises(ProviderError) as error:
        asyncio.run(run())
    assert error.value.error_type == "invalid_response"


def test_mock_provider_is_usable_without_credentials() -> None:
    provider = MockProvider(
        "fixture answer",
        model_id="fixture-model",
        usage=TokenUsage(input_tokens=2, output_tokens=3, total_tokens=5),
        estimated_cost_usd=0.001,
    )

    response = asyncio.run(provider.generate(GenerationRequest(prompt="question")))

    assert response.provider == "mock"
    assert response.text == "fixture answer"
    assert response.model_id == "fixture-model"
    assert response.usage.total_tokens == 5
    assert response.estimated_cost_usd == 0.001
    assert len(provider.requests) == 1


def test_factory_returns_only_adapters_with_configured_credentials() -> None:
    config = Settings(
        gemini_api_key="gemini-secret",
        groq_api_key="",
        minimax_api_key="",
        gemini_model_id="gemini-fixture",
        provider_timeout_seconds=7,
        provider_max_attempts=2,
        provider_max_retry_delay_seconds=1,
    )

    providers = create_configured_providers(config)

    assert list(providers) == ["gemini"]
    assert providers["gemini"].default_model_id == "gemini-fixture"  # type: ignore[attr-defined]


def test_groq_adapter_normalizes_response_and_usage() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization")
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-groq-123",
                "model": "llama-3.3-70b-versatile",
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "Groq response text"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 15,
                    "completion_tokens": 8,
                    "total_tokens": 23,
                },
            },
        )

    provider = GroqProvider(
        api_key="gsk-fixture-key",
        default_model_id="llama-3.3-70b-versatile",
        client=_client(handler),
    )

    response = asyncio.run(provider.generate(GenerationRequest(prompt="Hello Groq!")))

    assert response.provider == "groq"
    assert response.text == "Groq response text"
    assert response.model_id == "llama-3.3-70b-versatile"
    assert response.usage.input_tokens == 15
    assert response.usage.output_tokens == 8
    assert response.usage.total_tokens == 23
    assert seen["auth"] == "Bearer gsk-fixture-key"
    assert seen["body"]["model"] == "llama-3.3-70b-versatile"


def test_custom_openai_adapter_works_with_or_without_api_key() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(
            200,
            json={
                "id": "custom-1",
                "model": "local-llama",
                "choices": [{"message": {"role": "assistant", "content": "Local response"}}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7},
            },
        )

    # Local Ollama test without auth
    provider = create_custom_provider(
        base_url="http://localhost:11434/v1",
        api_key="",
        default_model_id="local-llama",
        name="Ollama Local",
        client=_client(handler),
    )

    response = asyncio.run(provider.generate(GenerationRequest(prompt="Test local")))

    assert response.text == "Local response"
    assert response.model_id == "local-llama"
    assert seen["url"] == "http://localhost:11434/v1/chat/completions"
    assert seen["auth"] is None


def test_factory_includes_groq_when_key_configured() -> None:
    config = Settings(
        gemini_api_key="",
        minimax_api_key="",
        groq_api_key="gsk-fixture",
        groq_model_id="llama-3.3-70b-versatile",
    )

    providers = create_configured_providers(config)

    assert "groq" in providers
    assert providers["groq"].default_model_id == "llama-3.3-70b-versatile"  # type: ignore[attr-defined]
