from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import Base, engine, get_db
from backend.evaluation.datasets import DatasetValidationError, load_dataset
from backend.evaluation.judge import build_configured_judge
from backend.evaluation.run_schemas import (
    CaseResultResponse,
    RunCreateRequest,
    RunDetailResponse,
    RunSummary,
)
from backend.evaluation.runner import execute_run
from backend.models import BenchmarkRun
from backend.providers import create_configured_providers

DATASETS_DIR = Path(__file__).resolve().parents[1] / "datasets"

app = FastAPI(
    title="End-to-End LLM Testing, Benchmarking and Regression Analysis",
    version="0.1.0",
    description="Modular evaluation, benchmarking, and regression analysis backend.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)


@app.get("/health")
def health_check() -> dict[str, object]:
    return {
        "status": "ok",
        "app": settings.app_name,
        "environment": settings.environment,
    }


@app.get("/ready")
def readiness_check() -> dict[str, object]:
    return {"status": "ready"}


@app.get("/api/config/providers")
def provider_status() -> dict[str, object]:
    return {
        "providers": {
            "gemini": {"configured": bool(settings.gemini_api_key)},
            "openrouter": {"configured": bool(settings.openrouter_api_key)},
        },
        "environment": settings.environment,
    }


@app.get("/api/overview")
def overview(db: Session = Depends(get_db)) -> dict[str, object]:
    total_runs = db.scalar(select(func.count()).select_from(BenchmarkRun)) or 0
    models_evaluated = (
        db.scalar(
            select(func.count(func.distinct(BenchmarkRun.model_id))).where(
                BenchmarkRun.status.in_(("completed", "partial_failure", "failed"))
            )
        )
        or 0
    )
    test_cases_executed = (
        db.scalar(select(func.coalesce(func.sum(BenchmarkRun.completed_cases), 0))) or 0
    )
    return {
        "project": settings.app_name,
        "status": "operational",
        "metrics": {
            "total_runs": total_runs,
            "models_evaluated": models_evaluated,
            "test_cases_executed": test_cases_executed,
        },
    }


def _run_summary(run: BenchmarkRun) -> dict[str, object]:
    return RunSummary(
        id=run.id,
        dataset_file=run.dataset_file,
        dataset_name=run.dataset_name,
        dataset_version=run.dataset_version,
        dataset_sha256=run.dataset_sha256,
        provider=run.provider,
        model_id=run.model_id,
        status=run.status,
        judge_enabled=run.judge_enabled,
        started_at=run.started_at.isoformat(),
        completed_at=run.completed_at.isoformat() if run.completed_at else None,
        total_cases=run.total_cases,
        completed_cases=run.completed_cases,
        passed_cases=run.passed_cases,
        errored_cases=run.errored_cases,
        total_input_tokens=run.total_input_tokens,
        total_output_tokens=run.total_output_tokens,
        total_latency_ms=run.total_latency_ms,
        total_estimated_cost_usd=run.total_estimated_cost_usd,
        error_message=run.error_message,
    ).model_dump(mode="json")


@app.post("/api/runs", response_model=RunSummary, status_code=201)
async def create_run(
    request: RunCreateRequest,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    dataset_path = DATASETS_DIR / request.dataset_file
    if not dataset_path.is_file():
        raise HTTPException(status_code=404, detail="Dataset file was not found.")
    try:
        dataset = load_dataset(dataset_path)
    except DatasetValidationError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid dataset: {exc}") from exc

    providers = create_configured_providers()
    provider = providers.get(request.provider)
    if provider is None:
        raise HTTPException(
            status_code=422,
            detail=f"Provider '{request.provider}' has no configured credentials.",
        )
    default_model_id = (
        settings.gemini_model_id if request.provider == "gemini" else settings.openrouter_model_id
    )
    model_id = request.model_id or default_model_id
    judge = None
    if request.include_judge:
        try:
            judge = build_configured_judge()
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if judge is None:
            raise HTTPException(
                status_code=422,
                detail="Judge is disabled. Set JUDGE_ENABLED=true before requesting judge scores.",
            )

    run = await execute_run(
        db,
        dataset=dataset,
        dataset_file=request.dataset_file,
        provider_name=request.provider,
        provider=provider,
        model_id=model_id,
        judge=judge,
    )
    return _run_summary(run)


@app.get("/api/runs", response_model=list[RunSummary])
def list_runs(
    limit: int = 50,
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    if not 1 <= limit <= 200:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 200")
    runs = db.scalars(
        select(BenchmarkRun).order_by(BenchmarkRun.started_at.desc()).limit(limit)
    ).all()
    return [_run_summary(run) for run in runs]


@app.get("/api/runs/{run_id}", response_model=RunDetailResponse)
def get_run(run_id: str, db: Session = Depends(get_db)) -> dict[str, object]:
    run = db.get(BenchmarkRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run was not found.")
    payload = _run_summary(run)
    payload["cases"] = [
        CaseResultResponse(
            id=case.id,
            ordinal=case.ordinal,
            test_case_id=case.test_case_id,
            evaluation_method=case.evaluation_method,
            status=case.status,
            candidate_text=case.candidate_text,
            provider=case.provider,
            model_id=case.model_id,
            input_tokens=case.input_tokens,
            output_tokens=case.output_tokens,
            latency_ms=case.latency_ms,
            estimated_cost_usd=case.estimated_cost_usd,
            deterministic_result=case.deterministic_result,
            semantic_result=case.semantic_result,
            judge_result=case.judge_result,
            evaluation_error=case.evaluation_error,
            error_category=case.error_category,
            error_message=case.error_message,
        ).model_dump(mode="json")
        for case in run.cases
    ]
    return payload
