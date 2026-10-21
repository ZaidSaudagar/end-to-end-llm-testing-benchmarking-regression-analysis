"""Dataset loading and deterministic evaluation primitives."""

from backend.evaluation.analysis import (
    MetricComparison,
    RunComparisonResult,
    compare_runs,
)
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
    "MetricComparison",
    "JudgeAggregate",
    "JudgeDimension",
    "JudgeOutcome",
    "JudgeRequest",
    "JudgeRubric",
    "JudgeRun",
    "JudgeScorecard",
    "RunComparisonResult",
    "SemanticScorer",
    "build_configured_judge",
    "compare_runs",
    "evaluate_case",
    "load_dataset",
]
