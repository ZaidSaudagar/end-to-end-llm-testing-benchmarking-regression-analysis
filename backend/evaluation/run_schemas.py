"""API schemas for starting and reading persisted benchmark runs."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RunCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_file: str = Field(min_length=1, max_length=255)
    provider: Literal["gemini", "openrouter"]
    model_id: str | None = Field(default=None, min_length=1, max_length=255)
    include_judge: bool = False

    @field_validator("dataset_file")
    @classmethod
    def safe_dataset_filename(cls, value: str) -> str:
        value = value.strip()
        if Path(value).name != value or value.startswith("."):
            raise ValueError("dataset_file must be a filename from the datasets directory")
        if Path(value).suffix.lower() not in {".csv", ".json"}:
            raise ValueError("dataset_file must end in .csv or .json")
        return value


class RunSummary(BaseModel):
    id: str
    dataset_file: str
    dataset_name: str
    dataset_version: str
    dataset_sha256: str
    provider: str
    model_id: str
    status: str
    judge_enabled: bool
    started_at: str
    completed_at: str | None
    total_cases: int
    completed_cases: int
    passed_cases: int
    errored_cases: int
    total_input_tokens: int | None
    total_output_tokens: int | None
    total_latency_ms: float
    total_estimated_cost_usd: float | None
    error_message: str | None = None


class CaseResultResponse(BaseModel):
    id: str
    ordinal: int
    test_case_id: str
    evaluation_method: str
    status: str
    candidate_text: str | None
    provider: str | None
    model_id: str | None
    input_tokens: int | None
    output_tokens: int | None
    latency_ms: float | None
    estimated_cost_usd: float | None
    deterministic_result: dict | None
    semantic_result: dict | None
    judge_result: dict | None
    evaluation_error: str | None
    error_category: str | None
    error_message: str | None


class RunDetailResponse(RunSummary):
    cases: list[CaseResultResponse]
