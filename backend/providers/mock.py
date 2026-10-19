"""Credential-free mock provider used in tests and local development."""

from __future__ import annotations

import time

from backend.providers.models import GenerationRequest, ProviderResponse, TokenUsage


class MockProvider:
    provider_name = "mock"

    def __init__(
        self,
        response_text: str = "Mock response",
        *,
        model_id: str = "mock-model",
        usage: TokenUsage | None = None,
        estimated_cost_usd: float | None = None,
    ) -> None:
        self.response_text = response_text
        self.model_id = model_id
        self.usage = usage or TokenUsage()
        self.estimated_cost_usd = estimated_cost_usd
        self.requests: list[GenerationRequest] = []

    async def generate(self, request: GenerationRequest) -> ProviderResponse:
        started = time.perf_counter()
        self.requests.append(request)
        return ProviderResponse(
            provider=self.provider_name,
            model_id=request.model_id or self.model_id,
            text=self.response_text,
            usage=self.usage,
            latency_ms=(time.perf_counter() - started) * 1000,
            finish_reason="mock_complete",
            request_id=f"mock-{len(self.requests)}",
            estimated_cost_usd=self.estimated_cost_usd,
        )
