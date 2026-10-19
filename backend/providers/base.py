"""Provider protocol, errors, retry handling, and shared HTTP behavior."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Awaitable, Callable, Protocol

import httpx

from backend.providers.models import GenerationRequest, ProviderResponse, TokenUsage


class ProviderError(RuntimeError):
    """Sanitized provider failure; never includes request headers or API keys."""

    def __init__(
        self,
        provider: str,
        error_type: str,
        message: str,
        *,
        retryable: bool = False,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.error_type = error_type
        self.retryable = retryable
        self.status_code = status_code


class Provider(Protocol):
    async def generate(self, request: GenerationRequest) -> ProviderResponse: ...


class CostEstimator(Protocol):
    """Optional interface for externally maintained, model-specific price tables."""

    def estimate_usd(
        self, model_id: str, input_tokens: int | None, output_tokens: int | None
    ) -> float | None: ...


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    initial_delay_seconds: float = 0.25
    max_delay_seconds: float = 2.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.initial_delay_seconds < 0 or self.max_delay_seconds < 0:
            raise ValueError("retry delays must be non-negative")

    def delay(self, attempt: int, retry_after: str | None = None) -> float:
        if retry_after:
            try:
                return min(self.max_delay_seconds, max(0.0, float(retry_after)))
            except ValueError:
                try:
                    retry_at = parsedate_to_datetime(retry_after)
                    if retry_at.tzinfo is None:
                        retry_at = retry_at.replace(tzinfo=timezone.utc)
                    remaining = (retry_at - datetime.now(timezone.utc)).total_seconds()
                    return min(self.max_delay_seconds, max(0.0, remaining))
                except (TypeError, ValueError, OverflowError):
                    pass
        return min(self.max_delay_seconds, self.initial_delay_seconds * (2**attempt))


Sleep = Callable[[float], Awaitable[None]]


class BaseHttpProvider:
    provider_name = "provider"

    def __init__(
        self,
        *,
        api_key: str,
        default_model_id: str,
        timeout_seconds: float = 30.0,
        retry_policy: RetryPolicy | None = None,
        cost_estimator: CostEstimator | None = None,
        client: httpx.AsyncClient | None = None,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        if not api_key.strip():
            raise ValueError(f"{self.provider_name} API key must not be blank")
        if not default_model_id.strip():
            raise ValueError(f"{self.provider_name} model ID must not be blank")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")
        self._api_key = api_key
        self.default_model_id = default_model_id
        self.timeout_seconds = timeout_seconds
        self.retry_policy = retry_policy or RetryPolicy()
        self.cost_estimator = cost_estimator
        self.client = client
        self._sleep = sleep

    async def generate(self, request: GenerationRequest) -> ProviderResponse:
        model_id = request.model_id or self.default_model_id
        payload = self._payload(request, model_id)
        started = time.perf_counter()
        response_data = await self._post_json(payload, self._headers())
        latency_ms = (time.perf_counter() - started) * 1000
        try:
            text, usage, finish_reason, response_model_id, request_id = self._normalize(
                response_data
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ProviderError(
                self.provider_name,
                "invalid_response",
                f"{self.provider_name} returned an unexpected response shape.",
            ) from exc
        estimated_cost = None
        if self.cost_estimator is not None:
            estimated_cost = self.cost_estimator.estimate_usd(
                response_model_id or model_id,
                usage.input_tokens,
                usage.output_tokens,
            )
        return ProviderResponse(
            provider=self.provider_name,
            model_id=response_model_id or model_id,
            text=text,
            usage=usage,
            latency_ms=latency_ms,
            finish_reason=finish_reason,
            request_id=request_id,
            estimated_cost_usd=estimated_cost,
        )

    async def _post_json(self, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
        if self.client is not None:
            return await self._send_with_retry(self.client, payload, headers)
        timeout = httpx.Timeout(self.timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            return await self._send_with_retry(client, payload, headers)

    async def _send_with_retry(
        self,
        client: httpx.AsyncClient,
        payload: dict[str, Any],
        headers: dict[str, str],
    ) -> dict[str, Any]:
        for attempt in range(self.retry_policy.max_attempts):
            try:
                response = await client.post(
                    self.endpoint(payload),
                    headers=headers,
                    json=self._http_body(payload),
                    timeout=self.timeout_seconds,
                )
            except httpx.TimeoutException as exc:
                if attempt + 1 < self.retry_policy.max_attempts:
                    await self._sleep(self.retry_policy.delay(attempt))
                    continue
                raise ProviderError(
                    self.provider_name,
                    "timeout",
                    f"{self.provider_name} request timed out after bounded retries.",
                    retryable=True,
                ) from exc
            except httpx.TransportError as exc:
                if attempt + 1 < self.retry_policy.max_attempts:
                    await self._sleep(self.retry_policy.delay(attempt))
                    continue
                raise ProviderError(
                    self.provider_name,
                    "transport",
                    f"{self.provider_name} transport failed after bounded retries.",
                    retryable=True,
                ) from exc

            if response.status_code in {408, 429} or response.status_code >= 500:
                if attempt + 1 < self.retry_policy.max_attempts:
                    await self._sleep(
                        self.retry_policy.delay(attempt, response.headers.get("Retry-After"))
                    )
                    continue
                if response.status_code == 408:
                    error_type = "timeout"
                elif response.status_code == 429:
                    error_type = "rate_limited"
                else:
                    error_type = "upstream_unavailable"
                raise ProviderError(
                    self.provider_name,
                    error_type,
                    (
                        f"{self.provider_name} returned HTTP {response.status_code} "
                        "after bounded retries."
                    ),
                    retryable=True,
                    status_code=response.status_code,
                )
            if response.is_error:
                error_type = (
                    "authentication" if response.status_code in {401, 403} else "request_rejected"
                )
                raise ProviderError(
                    self.provider_name,
                    error_type,
                    f"{self.provider_name} rejected the request with HTTP {response.status_code}.",
                    status_code=response.status_code,
                )
            try:
                data = response.json()
            except ValueError as exc:
                raise ProviderError(
                    self.provider_name,
                    "invalid_response",
                    f"{self.provider_name} returned invalid JSON.",
                    status_code=response.status_code,
                ) from exc
            if not isinstance(data, dict):
                raise ProviderError(
                    self.provider_name,
                    "invalid_response",
                    f"{self.provider_name} response must be a JSON object.",
                    status_code=response.status_code,
                )
            return data
        raise AssertionError("retry loop exited unexpectedly")

    def _usage(
        self,
        input_tokens: Any,
        output_tokens: Any,
        total_tokens: Any,
    ) -> TokenUsage:
        input_count = self._nonnegative_int(input_tokens)
        output_count = self._nonnegative_int(output_tokens)
        total_count = self._nonnegative_int(total_tokens)
        if total_count is None and input_count is not None and output_count is not None:
            total_count = input_count + output_count
        return TokenUsage(
            input_tokens=input_count,
            output_tokens=output_count,
            total_tokens=total_count,
        )

    @staticmethod
    def _nonnegative_int(value: Any) -> int | None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        if value < 0 or int(value) != value:
            return None
        return int(value)

    def _headers(self) -> dict[str, str]:
        raise NotImplementedError

    def endpoint(self, payload: dict[str, Any]) -> str:
        raise NotImplementedError

    def _http_body(self, payload: dict[str, Any]) -> dict[str, Any]:
        return payload

    def _payload(self, request: GenerationRequest, model_id: str) -> dict[str, Any]:
        raise NotImplementedError

    def _normalize(
        self, data: dict[str, Any]
    ) -> tuple[str, TokenUsage, str | None, str | None, str | None]:
        raise NotImplementedError
