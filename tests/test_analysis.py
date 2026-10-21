"""Tests for paired run comparisons and saved analysis endpoints."""

import uuid
from datetime import datetime, timezone

from backend.database import Base
from backend.evaluation.analysis import _holm_adjust, compare_runs
from backend.models import BenchmarkCaseResult, BenchmarkRun
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool


def make_run(
    run_id: str,
    *,
    pass_values: list[bool] | None = None,
    semantic_values: list[float] | None = None,
    judge_values: list[float] | None = None,
    dataset_hash: str = "f" * 64,
) -> BenchmarkRun:
    count = max(len(pass_values or []), len(semantic_values or []), len(judge_values or []), 0)
    run = BenchmarkRun(
        id=run_id,
        dataset_file="benchmark.csv",
        dataset_name="benchmark",
        dataset_version="1.0",
        dataset_sha256=dataset_hash,
        provider="mock",
        model_id=run_id,
        status="completed",
        judge_enabled=bool(judge_values),
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        total_cases=count,
        completed_cases=count,
        passed_cases=sum(pass_values or []),
        errored_cases=0,
        total_input_tokens=0,
        total_output_tokens=0,
        total_latency_ms=0,
        total_estimated_cost_usd=0,
    )
    run.cases = []
    for index in range(count):
        judge_result = None
        if judge_values is not None:
            value = judge_values[index]
            judge_result = {
                "aggregate": {
                    "overall_mean": value,
                    "dimension_means": {"relevance": value},
                }
            }
        run.cases.append(
            BenchmarkCaseResult(
                id=str(uuid.uuid4()),
                run_id=run_id,
                ordinal=index + 1,
                test_case_id=f"case-{index}",
                evaluation_method="exact_match",
                status="completed",
                deterministic_result=(
                    {"passed": pass_values[index]} if pass_values is not None else None
                ),
                semantic_result=(
                    {"similarity": semantic_values[index]} if semantic_values is not None else None
                ),
                judge_result=judge_result,
            )
        )
    return run


def test_paired_binary_regression_uses_exact_mcnemar_and_bootstrap_ci() -> None:
    baseline = make_run("baseline", pass_values=[True] * 10)
    candidate = make_run("candidate", pass_values=[False] * 10)
    result = compare_runs(baseline, candidate)
    metric = result.metrics[0]
    assert metric.metric == "deterministic_pass_rate"
    assert metric.paired_cases == 10
    assert metric.baseline_mean == 1
    assert metric.candidate_mean == 0
    assert metric.mean_delta == -1
    assert metric.confidence_interval_95 == (-1, -1)
    assert metric.adjusted_p_value == metric.p_value
    assert metric.regression_detected is True


def test_continuous_metrics_are_paired_and_judge_dimensions_are_included() -> None:
    baseline = make_run(
        "baseline",
        semantic_values=[0.8, 0.7, 0.9, 0.8],
        judge_values=[4.0, 4.0, 4.0, 4.0],
    )
    candidate = make_run(
        "candidate",
        semantic_values=[0.9, 0.8, 0.9, 0.9],
        judge_values=[3.0, 3.0, 3.0, 3.0],
    )
    result = compare_runs(baseline, candidate)
    metrics = {item.metric: item for item in result.metrics}
    assert metrics["semantic_similarity"].mean_delta == 0.075
    assert metrics["judge_overall"].mean_delta == -1
    assert metrics["judge_relevance"].paired_cases == 4


def test_single_pair_is_reported_without_claiming_significance() -> None:
    result = compare_runs(
        make_run("baseline", pass_values=[True]),
        make_run("candidate", pass_values=[False]),
    )
    metric = result.metrics[0]
    assert metric.paired_cases == 1
    assert metric.p_value is None
    assert metric.confidence_interval_95 is None
    assert metric.regression_detected is False


def test_dataset_mismatch_and_same_run_are_rejected() -> None:
    baseline = make_run("baseline", pass_values=[True])
    with_hash = make_run("candidate", pass_values=[False], dataset_hash="a" * 64)
    try:
        compare_runs(baseline, baseline)
        raise AssertionError("same-run comparison should fail")
    except ValueError as exc:
        assert "different runs" in str(exc)
    try:
        compare_runs(baseline, with_hash)
        raise AssertionError("dataset mismatch should fail")
    except ValueError as exc:
        assert "same dataset fingerprint" in str(exc)


def test_holm_correction_is_monotonic_in_sorted_p_value_order() -> None:
    adjusted = _holm_adjust([0.04, 0.01, 0.2, None])
    assert adjusted == [0.08, 0.03, 0.2, None]


def test_analysis_api_persists_and_returns_comparison(tmp_path, monkeypatch) -> None:
    from backend import main
    from backend.database import get_db

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    db = Session(engine)
    baseline = make_run("baseline-api", pass_values=[True] * 8)
    candidate = make_run("candidate-api", pass_values=[False] * 8)
    db.add_all([baseline, candidate])
    db.commit()

    def override_get_db():
        yield db

    main.app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(main.app) as client:
            response = client.post(
                "/api/analyses/compare",
                json={"baseline_run_id": "baseline-api", "candidate_run_id": "candidate-api"},
            )
            assert response.status_code == 201, response.text
            payload = response.json()
            assert payload["result"]["metrics"][0]["regression_detected"] is True
            analysis_id = payload["id"]
            loaded = client.get(f"/api/analyses/{analysis_id}")
            assert loaded.status_code == 200
            assert loaded.json()["result"]["candidate_run_id"] == "candidate-api"
            assert client.get("/api/analyses").json()[0]["id"] == analysis_id
    finally:
        main.app.dependency_overrides.pop(get_db, None)
        db.close()
        engine.dispose()
