"""Paired run comparison with reproducible uncertainty and regression signals."""

from __future__ import annotations

import hashlib

import numpy as np
from pydantic import BaseModel, ConfigDict, Field
from scipy.stats import binomtest, wilcoxon

from backend.models import BenchmarkRun

ANALYSIS_METHOD_VERSION = "paired-run-comparison-v1"
BOOTSTRAP_SAMPLES = 10_000
JUDGE_DIMENSIONS = (
    "relevance",
    "completeness",
    "instruction_following",
    "factual_alignment",
    "clarity",
)


class MetricComparison(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric: str
    statistical_test: str
    higher_is_better: bool = True
    paired_cases: int = Field(ge=1)
    baseline_mean: float
    candidate_mean: float
    mean_delta: float
    confidence_interval_95: tuple[float, float] | None
    p_value: float | None
    adjusted_p_value: float | None = None
    regression_detected: bool = False


class RunComparisonResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method_version: str = ANALYSIS_METHOD_VERSION
    baseline_run_id: str
    candidate_run_id: str
    dataset_name: str
    dataset_version: str
    dataset_sha256: str
    alpha: float
    minimum_regression_drop: float
    multiple_testing_correction: str = "Holm-Bonferroni"
    confidence_interval_method: str = "paired percentile bootstrap"
    metrics: list[MetricComparison]


def _extract_metrics(run: BenchmarkRun) -> dict[str, dict[str, float]]:
    values: dict[str, dict[str, float]] = {}
    for case in run.cases:
        if case.status != "completed":
            continue
        case_metrics: dict[str, float] = {}
        deterministic = case.deterministic_result or {}
        passed = deterministic.get("passed")
        if isinstance(passed, bool):
            case_metrics["deterministic_pass_rate"] = float(passed)

        semantic = case.semantic_result or {}
        similarity = semantic.get("similarity")
        if isinstance(similarity, (int, float)) and not isinstance(similarity, bool):
            case_metrics["semantic_similarity"] = float(similarity)

        judge = case.judge_result or {}
        aggregate = judge.get("aggregate") or {}
        overall = aggregate.get("overall_mean")
        if isinstance(overall, (int, float)) and not isinstance(overall, bool):
            case_metrics["judge_overall"] = float(overall)
        dimension_means = aggregate.get("dimension_means") or {}
        for dimension in JUDGE_DIMENSIONS:
            score = dimension_means.get(dimension)
            if isinstance(score, (int, float)) and not isinstance(score, bool):
                case_metrics[f"judge_{dimension}"] = float(score)
        if case_metrics:
            values[case.test_case_id] = case_metrics
    return values


def _paired_bootstrap_ci(
    differences: np.ndarray,
    *,
    alpha: float,
    seed_text: str,
) -> tuple[float, float]:
    digest = hashlib.sha256(seed_text.encode("utf-8")).digest()
    rng = np.random.default_rng(int.from_bytes(digest[:8], "big"))
    bootstrap_means = np.empty(BOOTSTRAP_SAMPLES, dtype=np.float64)
    # Chunk the resampling matrix so large datasets do not require a huge temporary array.
    for start in range(0, BOOTSTRAP_SAMPLES, 128):
        stop = min(start + 128, BOOTSTRAP_SAMPLES)
        indexes = rng.integers(0, len(differences), size=(stop - start, len(differences)))
        bootstrap_means[start:stop] = differences[indexes].mean(axis=1)
    low, high = np.quantile(bootstrap_means, [alpha / 2, 1 - alpha / 2])
    return round(float(low), 6), round(float(high), 6)


def _paired_p_value(metric: str, differences: np.ndarray) -> float | None:
    if len(differences) < 2:
        return None
    if metric == "deterministic_pass_rate":
        losses = int(np.sum(differences < 0))
        gains = int(np.sum(differences > 0))
        discordant = losses + gains
        return 1.0 if discordant == 0 else float(binomtest(min(losses, gains), discordant).pvalue)
    if np.all(differences == 0):
        return 1.0
    return float(wilcoxon(differences, alternative="two-sided", method="auto").pvalue)


def _holm_adjust(p_values: list[float | None]) -> list[float | None]:
    valid = [(index, value) for index, value in enumerate(p_values) if value is not None]
    valid.sort(key=lambda item: item[1])
    adjusted: list[float | None] = [None] * len(p_values)
    running_max = 0.0
    count = len(valid)
    for rank, (index, value) in enumerate(valid):
        running_max = max(running_max, min(1.0, (count - rank) * value))
        adjusted[index] = running_max
    return adjusted


def compare_runs(
    baseline: BenchmarkRun,
    candidate: BenchmarkRun,
    *,
    alpha: float = 0.05,
    minimum_regression_drop: float = 0.0,
) -> RunComparisonResult:
    """Compare common completed cases. Positive deltas always favor the candidate."""
    if baseline.id == candidate.id:
        raise ValueError("baseline and candidate must be different runs")
    if baseline.dataset_sha256 != candidate.dataset_sha256:
        raise ValueError("runs must use the same dataset fingerprint")
    if not 0 < alpha < 1:
        raise ValueError("alpha must be between 0 and 1")
    if minimum_regression_drop < 0:
        raise ValueError("minimum_regression_drop must be non-negative")

    baseline_values = _extract_metrics(baseline)
    candidate_values = _extract_metrics(candidate)
    metric_names = sorted(
        set().union(*(metrics.keys() for metrics in baseline_values.values()))
        & set().union(*(metrics.keys() for metrics in candidate_values.values()))
    )
    comparisons: list[MetricComparison] = []
    for metric in metric_names:
        case_ids = sorted(
            case_id
            for case_id in baseline_values.keys() & candidate_values.keys()
            if metric in baseline_values[case_id] and metric in candidate_values[case_id]
        )
        if not case_ids:
            continue
        baseline_scores = np.asarray(
            [baseline_values[case_id][metric] for case_id in case_ids], dtype=np.float64
        )
        candidate_scores = np.asarray(
            [candidate_values[case_id][metric] for case_id in case_ids], dtype=np.float64
        )
        differences = candidate_scores - baseline_scores
        p_value = _paired_p_value(metric, differences)
        confidence_interval = (
            _paired_bootstrap_ci(
                differences,
                alpha=alpha,
                seed_text=f"{baseline.id}:{candidate.id}:{metric}",
            )
            if len(differences) >= 2
            else None
        )
        comparisons.append(
            MetricComparison(
                metric=metric,
                statistical_test=(
                    "exact McNemar test"
                    if metric == "deterministic_pass_rate"
                    else "Wilcoxon signed-rank test"
                ),
                paired_cases=len(case_ids),
                baseline_mean=round(float(baseline_scores.mean()), 6),
                candidate_mean=round(float(candidate_scores.mean()), 6),
                mean_delta=round(float(differences.mean()), 6),
                confidence_interval_95=confidence_interval,
                p_value=p_value,
            )
        )

    adjusted = _holm_adjust([metric.p_value for metric in comparisons])
    for metric, adjusted_p in zip(comparisons, adjusted, strict=True):
        metric.adjusted_p_value = adjusted_p
        metric.regression_detected = bool(
            adjusted_p is not None
            and adjusted_p < alpha
            and metric.mean_delta < -minimum_regression_drop
        )

    return RunComparisonResult(
        baseline_run_id=baseline.id,
        candidate_run_id=candidate.id,
        dataset_name=baseline.dataset_name,
        dataset_version=baseline.dataset_version,
        dataset_sha256=baseline.dataset_sha256,
        alpha=alpha,
        minimum_regression_drop=minimum_regression_drop,
        metrics=comparisons,
    )
