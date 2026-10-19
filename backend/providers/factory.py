"""Construct only providers that have credentials configured."""

from __future__ import annotations

from typing import Any

from backend.config import Settings, settings
from backend.providers.base import Provider, RetryPolicy
from backend.providers.gemini import GeminiProvider
from backend.providers.openrouter import OpenRouterProvider


def create_configured_providers(
    config: Settings = settings,
    *,
    client: Any = None,
) -> dict[str, Provider]:
    """Return adapters for configured credentials without exposing key material."""
    retry_policy = RetryPolicy(
        max_attempts=config.provider_max_attempts,
        max_delay_seconds=config.provider_max_retry_delay_seconds,
    )
    providers: dict[str, Provider] = {}
    if config.gemini_api_key.strip():
        providers["gemini"] = GeminiProvider(
            api_key=config.gemini_api_key,
            default_model_id=config.gemini_model_id,
            timeout_seconds=config.provider_timeout_seconds,
            retry_policy=retry_policy,
            client=client,
        )
    if config.openrouter_api_key.strip():
        providers["openrouter"] = OpenRouterProvider(
            api_key=config.openrouter_api_key,
            default_model_id=config.openrouter_model_id,
            timeout_seconds=config.provider_timeout_seconds,
            retry_policy=retry_policy,
            client=client,
        )
    return providers
