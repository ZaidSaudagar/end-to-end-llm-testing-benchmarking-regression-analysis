"""Offline tests for provider-backed execution and persisted run history."""

import asyncio
import json

from backend.database import Base
from backend.evaluation.datasets import DatasetDocument
from backend.evaluation.judge import LLMJudge
from backend.evaluation.runner import execute_run
from backend.evaluation.schemas import DatasetCase, SemanticScore
from backend.models import BenchmarkCaseResult
from backend.providers import (
    GenerationRequest,
    MockProvider,
    ProviderError,
    ProviderResponse,
    TokenUsage,
)
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool


def database() -> tuple[object, Session]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine, Session(engine)


def make_dataset(*methods: str) -> DatasetDocument:
    cases = [
        DatasetCase(
            test_case_id=f"case-{index}",
            task_category="test",
            input_prompt=f"Prompt {index}",
            evaluation_method=method,
            dataset_version="1.0",
            reference_answer="answer",
            reference_context="answer reference",
        )
        for index, method in enumerate(methods, start=1)
    ]
    return DatasetDocument(
        dataset_name="test data",
        dataset_version="1.0",
        source_sha256="a" * 64,
        cases=cases,
    )


class SequencedProvider:
    provider_name = "sequenced"

    def __init__(self, results: list[str | Exception]) -> None:
        self.results = results

    async def generate(self, request: GenerationRequest) -> ProviderResponse:
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return ProviderResponse(
            provider=self.provider_name,
            model_id=request.model_id or "test-model",
            text=result,
            usage=TokenUsage(input_tokens=5, output_tokens=2, total_tokens=7),
            latency_ms=10,
            estimated_cost_usd=0.001,
        )


class FakeSemanticScorer:
    def score_batch(self, references, candidates, *, test_case_ids=None, batch_size=32):
        return [
            SemanticScore(
                test_case_id=test_case_ids[0],
                similarity=0.91,
                model_id="fake-embedder",
                model_revision="fake-revision",
                embedding_library_version="test",
            )
        ]


def test_run_executes_cases_and_persists_metrics_and_source_fingerprint() -> None:
    engine, db = database()
    try:
        run = asyncio.run(
            execute_run(
                db,
                dataset=make_dataset("exact_match", "exact_match"),
                dataset_file="benchmark.csv",
                provider_name="mock",
                provider=MockProvider(
                    "answer",
                    usage=TokenUsage(input_tokens=5, output_tokens=2, total_tokens=7),
                    estimated_cost_usd=0.001,
                ),
                model_id="test-model",
            )
        )
        results = db.scalars(
            select(BenchmarkCaseResult).where(BenchmarkCaseResult.run_id == run.id)
        ).all()
        assert run.status == "completed"
        assert run.completed_cases == 2
        assert run.passed_cases == 2
        assert run.total_input_tokens == 10
        assert run.total_output_tokens == 4
        assert run.total_estimated_cost_usd == 0.002
        assert run.dataset_sha256 == "a" * 64
        assert len(results) == 2
        assert results[0].deterministic_result["passed"] is True
        assert results[0].candidate_text == "answer"
    finally:
        db.close()
        engine.dispose()


def test_provider_failure_is_persisted_and_run_continues() -> None:
    engine, db = database()
    try:
        provider = SequencedProvider(
            ["answer", ProviderError("sequenced", "rate_limited", "sanitized")]
        )
        run = asyncio.run(
            execute_run(
                db,
                dataset=make_dataset("exact_match", "exact_match"),
                dataset_file="benchmark.csv",
                provider_name="sequenced",
                provider=provider,
                model_id="test-model",
            )
        )
        cases = db.scalars(
            select(BenchmarkCaseResult)
            .where(BenchmarkCaseResult.run_id == run.id)
            .order_by(BenchmarkCaseResult.ordinal)
        ).all()
        assert run.status == "partial_failure"
        assert run.completed_cases == 1
        assert run.errored_cases == 1
        assert cases[1].status == "error"
        assert cases[1].error_category == "rate_limited"
        assert "sanitized" not in (cases[1].error_message or "")
    finally:
        db.close()
        engine.dispose()


def test_judge_outcome_is_saved_for_judge_only_evaluation_methods() -> None:
    engine, db = database()
    try:
        judge_payload = json.dumps(
            {
                "relevance": {"score": 4, "rationale": "Relevant."},
                "completeness": {"score": 4, "rationale": "Complete."},
                "instruction_following": {"score": 4, "rationale": "Follows task."},
                "factual_alignment": {"score": 5, "rationale": "Matches references."},
                "clarity": {"score": 4, "rationale": "Clear."},
            }
        )
        run = asyncio.run(
            execute_run(
                db,
                dataset=make_dataset("reference_grounding"),
                dataset_file="grounding.json",
                provider_name="mock",
                provider=MockProvider("answer"),
                model_id="candidate-model",
                judge=LLMJudge(MockProvider(judge_payload), "judge-model"),
            )
        )
        case = db.scalar(select(BenchmarkCaseResult).where(BenchmarkCaseResult.run_id == run.id))
        assert run.judge_enabled is True
        assert run.completed_cases == 1
        assert case.deterministic_result is None
        assert case.judge_result["status"] == "success"
        assert case.judge_result["runs"][0]["rubric_version"] == "llm-judge-rubric-v1"
    finally:
        db.close()
        engine.dispose()


def test_all_provider_errors_mark_run_failed() -> None:
    engine, db = database()
    try:
        run = asyncio.run(
            execute_run(
                db,
                dataset=make_dataset("exact_match"),
                dataset_file="benchmark.csv",
                provider_name="sequenced",
                provider=SequencedProvider([ProviderError("sequenced", "timeout", "sanitized")]),
                model_id="test-model",
            )
        )
        assert run.status == "failed"
        assert run.errored_cases == 1
        assert run.error_message == "All provider requests failed."
    finally:
        db.close()
        engine.dispose()


def test_semantic_method_is_persisted_as_similarity_not_correctness() -> None:
    engine, db = database()
    try:
        run = asyncio.run(
            execute_run(
                db,
                dataset=make_dataset("semantic_similarity"),
                dataset_file="semantic.csv",
                provider_name="mock",
                provider=MockProvider("a paraphrase"),
                model_id="test-model",
                semantic_scorer=FakeSemanticScorer(),
            )
        )
        case = db.scalar(select(BenchmarkCaseResult).where(BenchmarkCaseResult.run_id == run.id))
        assert case.semantic_result["similarity"] == 0.91
        assert case.deterministic_result is None
        assert run.passed_cases == 0
    finally:
        db.close()
        engine.dispose()


def test_run_api_creates_and_reads_persisted_run(tmp_path, monkeypatch) -> None:
    from backend import main
    from backend.database import get_db

    engine, db = database()
    dataset_file = tmp_path / "one_case.csv"
    dataset_file.write_text(
        "test_case_id,task_category,input_prompt,reference_answer,evaluation_method,dataset_version\n"
        "case-api,test,Prompt,answer,exact_match,1.0\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(main, "DATASETS_DIR", tmp_path)
    monkeypatch.setattr(
        main,
        "create_configured_providers",
        lambda: {"minimax": MockProvider("answer")},
    )

    def override_get_db():
        try:
            yield db
        finally:
            pass

    main.app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(main.app) as client:
            created = client.post(
                "/api/runs",
                json={"dataset_file": "one_case.csv", "provider": "minimax"},
            )
            assert created.status_code == 201, created.text
            summary = created.json()
            assert summary["status"] == "completed"
            assert summary["completed_cases"] == 1
            detail = client.get(f"/api/runs/{summary['id']}")
            assert detail.status_code == 200
            assert detail.json()["cases"][0]["deterministic_result"]["passed"] is True
            assert client.get("/api/runs").json()[0]["id"] == summary["id"]
            unsafe = client.post(
                "/api/runs",
                json={"dataset_file": "../one_case.csv", "provider": "minimax"},
            )
            assert unsafe.status_code == 422
    finally:
        main.app.dependency_overrides.pop(get_db, None)
        db.close()
        engine.dispose()
