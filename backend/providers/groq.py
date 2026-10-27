"""Adapter for Groq's ultra-fast OpenAI-compatible chat completions endpoint."""

from __future__ import annotations

from typing import Any

from backend.providers.base import BaseHttpProvider
from backend.providers.models import GenerationRequest, TokenUsage


class GroqProvider(BaseHttpProvider):
    provider_name = "groq"

    def __init__(self, *, base_url: str | None = None, **kwargs: Any):
        super().__init__(**kwargs)
        self.base_url = (base_url or "https://api.groq.com/openai/v1").rstrip("/")

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    def endpoint(self, payload: dict[str, Any]) -> str:
        return f"{self.base_url}/chat/completions"

    def _payload(self, request: GenerationRequest, model_id: str) -> dict[str, Any]:
        messages: list[dict[str, str]] = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.prompt})
        payload: dict[str, Any] = {"model": model_id, "messages": messages}
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.max_output_tokens is not None:
            payload["max_tokens"] = request.max_output_tokens
        return payload

    def _normalize(
        self, data: dict[str, Any]
    ) -> tuple[str, TokenUsage, str | None, str | None, str | None]:
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise ValueError("Groq response did not contain a chat completion choice")
        choice = choices[0]
        message = choice.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            text = "".join(
                part["text"]
                for part in content
                if isinstance(part, dict)
                and part.get("type") == "text"
                and isinstance(part.get("text"), str)
            )
        else:
            text = ""

        usage_data = data.get("usage")
        usage_data = usage_data if isinstance(usage_data, dict) else {}
        usage = self._usage(
            usage_data.get("prompt_tokens"),
            usage_data.get("completion_tokens"),
            usage_data.get("total_tokens"),
        )
        model_id = data.get("model")
        finish_reason = choice.get("finish_reason")
        request_id = data.get("id")
        return (
            text,
            usage,
            finish_reason if isinstance(finish_reason, str) else None,
            model_id if isinstance(model_id, str) else None,
            request_id if isinstance(request_id, str) else None,
        )
