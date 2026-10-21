"""API contracts for statistical comparison of two saved runs."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.evaluation.analysis import RunComparisonResult


class RunComparisonRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    baseline_run_id: str = Field(min_length=1, max_length=36)
    candidate_run_id: str = Field(min_length=1, max_length=36)
    alpha: float = Field(default=0.05, gt=0, lt=1)
    minimum_regression_drop: float = Field(default=0.0, ge=0)

    @model_validator(mode="after")
    def distinct_runs(self) -> RunComparisonRequest:
        if self.baseline_run_id == self.candidate_run_id:
            raise ValueError("baseline_run_id and candidate_run_id must differ")
        return self


class RunAnalysisResponse(BaseModel):
    id: str
    created_at: str
    result: RunComparisonResult


class RunAnalysisListItem(BaseModel):
    id: str
    created_at: str
    baseline_run_id: str
    candidate_run_id: str
    method_version: str
    metric_count: int
    regressions_detected: int
