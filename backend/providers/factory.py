"""Construct only providers that have credentials configured."""

from __future__ import annotations

from typing import Any

from backend.config import Settings, settings
from backend.providers.base import Provider, RetryPolicy
from backend.providers.custom import CustomOpenAIProvider
from backend.providers.gemini import GeminiProvider
from backend.providers.groq import GroqProvider
from backend.providers.minimax import MiniMaxProvider


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
    if config.minimax_api_key.strip():
        providers["minimax"] = MiniMaxProvider(
            api_key=config.minimax_api_key,
            default_model_id=config.minimax_model_id,
            base_url=config.minimax_base_url,
            timeout_seconds=config.provider_timeout_seconds,
            retry_policy=retry_policy,
            client=client,
        )
    if config.groq_api_key.strip():
        providers["groq"] = GroqProvider(
            api_key=config.groq_api_key,
            default_model_id=config.groq_model_id,
            base_url=config.groq_base_url,
            timeout_seconds=config.provider_timeout_seconds,
            retry_policy=retry_policy,
            client=client,
        )
    return providers


def create_custom_provider(
    *,
    base_url: str,
    api_key: str = "",
    default_model_id: str,
    name: str = "custom",
    config: Settings = settings,
    client: Any = None,
) -> CustomOpenAIProvider:
    """Create an ad-hoc or user-registered OpenAI-compatible provider."""
    retry_policy = RetryPolicy(
        max_attempts=config.provider_max_attempts,
        max_delay_seconds=config.provider_max_retry_delay_seconds,
    )
    return CustomOpenAIProvider(
        base_url=base_url,
        api_key=api_key,
        default_model_id=default_model_id,
        custom_provider_name=name,
        timeout_seconds=config.provider_timeout_seconds,
        retry_policy=retry_policy,
        client=client,
    )
