"""Adapter for Google's Gemini generateContent REST API."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from backend.providers.base import BaseHttpProvider
from backend.providers.models import GenerationRequest, TokenUsage


class GeminiProvider(BaseHttpProvider):
    provider_name = "gemini"
    base_url = "https://generativelanguage.googleapis.com/v1beta"

    def _headers(self) -> dict[str, str]:
        return {"x-goog-api-key": self._api_key, "Content-Type": "application/json"}

    def endpoint(self, payload: dict[str, Any]) -> str:
        model_id = quote(str(payload["model"]), safe="-._")
        return f"{self.base_url}/models/{model_id}:generateContent"

    def _http_body(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in payload.items() if key != "model"}

    def _payload(self, request: GenerationRequest, model_id: str) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": model_id.removeprefix("models/"),
            "contents": [{"role": "user", "parts": [{"text": request.prompt}]}],
        }
        if request.system_prompt:
            payload["systemInstruction"] = {"parts": [{"text": request.system_prompt}]}
        generation_config: dict[str, Any] = {}
        if request.temperature is not None:
            generation_config["temperature"] = request.temperature
        if request.max_output_tokens is not None:
            generation_config["maxOutputTokens"] = request.max_output_tokens
        if generation_config:
            payload["generationConfig"] = generation_config
        return payload

    def _normalize(
        self, data: dict[str, Any]
    ) -> tuple[str, TokenUsage, str | None, str | None, str | None]:
        candidates = data.get("candidates")
        finish_reason: str | None = None
        text = ""
        if isinstance(candidates, list) and candidates:
            candidate = candidates[0]
            if isinstance(candidate, dict):
                finish_reason = self._as_text(candidate.get("finishReason"))
                content = candidate.get("content")
                parts = content.get("parts") if isinstance(content, dict) else None
                if isinstance(parts, list):
                    text = "".join(
                        part["text"]
                        for part in parts
                        if isinstance(part, dict) and isinstance(part.get("text"), str)
                    )
        else:
            feedback = data.get("promptFeedback")
            if isinstance(feedback, dict):
                finish_reason = self._as_text(feedback.get("blockReason"))
            if finish_reason is None:
                raise ValueError("Gemini response did not contain candidates or a block reason")

        usage_data = data.get("usageMetadata")
        usage_data = usage_data if isinstance(usage_data, dict) else {}
        usage = self._usage(
            usage_data.get("promptTokenCount"),
            usage_data.get("candidatesTokenCount"),
            usage_data.get("totalTokenCount"),
        )
        return (
            text,
            usage,
            finish_reason,
            self._as_text(data.get("modelVersion")),
            self._as_text(data.get("responseId")),
        )

    @staticmethod
    def _as_text(value: Any) -> str | None:
        return value if isinstance(value, str) and value else None
