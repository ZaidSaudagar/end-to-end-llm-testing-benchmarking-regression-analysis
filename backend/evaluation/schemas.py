"""Typed schemas for benchmark datasets and deterministic evaluation results."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DatasetCase(BaseModel):
    model_config = ConfigDict(extra="allow")

    test_case_id: str = Field(min_length=1)
    task_category: str = Field(min_length=1)
    input_prompt: str = Field(min_length=1)
    evaluation_method: str = Field(min_length=1)
    dataset_version: str = Field(min_length=1)
    reference_answer: str | None = None
    reference_context: str | None = None
    expected_output: Any | None = None
    expected_output_schema: dict[str, Any] | None = None
    expected_behavior: str | None = None
    difficulty: str | None = None
    tags: list[str] = Field(default_factory=list)

    @field_validator(
        "test_case_id", "task_category", "input_prompt", "evaluation_method", "dataset_version"
    )
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class DatasetDocument(BaseModel):
    model_config = ConfigDict(extra="allow")

    dataset_name: str = Field(min_length=1)
    dataset_version: str = Field(min_length=1)
    description: str = ""
    source_sha256: str
    cases: list[DatasetCase] = Field(min_length=1)


class EvaluationResult(BaseModel):
    test_case_id: str
    evaluation_method: str
    passed: bool
    score: float = Field(ge=0, le=1)
    expected: Any | None = None
    actual: Any | None = None
    details: str = ""


class SemanticScore(BaseModel):
    """Cosine similarity metadata; this score is not a correctness probability."""

    test_case_id: str | None = None
    similarity: float | None = Field(default=None, ge=-1, le=1)
    metric: str = "cosine_similarity"
    model_id: str
    model_revision: str
    embedding_library_version: str
    details: str = ""
