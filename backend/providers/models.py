"""Normalized request and response data models shared by provider adapters."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class GenerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(min_length=1)
    model_id: str | None = None
    system_prompt: str | None = None
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_output_tokens: int | None = Field(default=None, gt=0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("prompt", "system_prompt")
    @classmethod
    def strip_prompts(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("prompt fields must not be blank")
        return value

    @field_validator("model_id")
    @classmethod
    def strip_model_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("model_id must not be blank")
        return value


class TokenUsage(BaseModel):
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)


class ProviderResponse(BaseModel):
    provider: str
    model_id: str
    text: str
    usage: TokenUsage = Field(default_factory=TokenUsage)
    latency_ms: float = Field(ge=0)
    finish_reason: str | None = None
    request_id: str | None = None
    estimated_cost_usd: float | None = Field(default=None, ge=0)
