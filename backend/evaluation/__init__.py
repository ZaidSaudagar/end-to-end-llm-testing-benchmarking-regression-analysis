"""Dataset loading and deterministic evaluation primitives."""

from backend.evaluation.datasets import DatasetDocument, DatasetValidationError, load_dataset
from backend.evaluation.judge import (
    DEFAULT_RUBRIC,
    JudgeAggregate,
    JudgeDimension,
    JudgeOutcome,
    JudgeRequest,
    JudgeRubric,
    JudgeRun,
    JudgeScorecard,
    LLMJudge,
    build_configured_judge,
)
from backend.evaluation.metrics import evaluate_case
from backend.evaluation.semantic import SemanticScorer

__all__ = [
    "DatasetDocument",
    "DatasetValidationError",
    "DEFAULT_RUBRIC",
    "LLMJudge",
    "JudgeAggregate",
    "JudgeDimension",
    "JudgeOutcome",
    "JudgeRequest",
    "JudgeRubric",
    "JudgeRun",
    "JudgeScorecard",
    "SemanticScorer",
    "build_configured_judge",
    "evaluate_case",
    "load_dataset",
]
