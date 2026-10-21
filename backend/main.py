from __future__ import annotations

import hmac
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.middleware.trustedhost import TrustedHostMiddleware

from backend.config import settings
from backend.database import Base, engine, get_db
from backend.evaluation.analysis import compare_runs
from backend.evaluation.analysis_schemas import (
    RunAnalysisListItem,
    RunAnalysisResponse,
    RunComparisonRequest,
)
from backend.evaluation.datasets import DatasetValidationError, load_dataset
from backend.evaluation.judge import build_configured_judge
from backend.evaluation.run_schemas import (
    CaseResultResponse,
    RunCreateRequest,
    RunDetailResponse,
    RunSummary,
)
from backend.evaluation.runner import execute_run
from backend.models import BenchmarkRun, RunAnalysis
from backend.providers import create_configured_providers

DATASETS_DIR = Path(__file__).resolve().parents[1] / "datasets"
logger = logging.getLogger(__name__)
is_production = settings.environment.strip().lower() == "production"

app = FastAPI(
    title="End-to-End LLM Testing, Benchmarking and Regression Analysis",
    version="0.1.0",
    description="Modular evaluation, benchmarking, and regression analysis backend.",
    debug=settings.debug,
    docs_url=None if is_production else "/docs",
    redoc_url=None if is_production else "/redoc",
    openapi_url=None if is_production else "/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
if is_production:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(settings.allowed_hosts))

Base.metadata.create_all(bind=engine)


@app.middleware("http")
async def protect_api(request: Request, call_next):
    if request.method == "OPTIONS" or not request.url.path.startswith("/api/"):
        return await call_next(request)
    expected_key = settings.backend_api_key
    if expected_key and not hmac.compare_digest(
        request.headers.get("x-api-key", ""), expected_key
    ):
        return JSONResponse(status_code=401, content={"detail": "Invalid or missing API key."})
    raw_content_length = request.headers.get("content-length")
    if raw_content_length:
        try:
            content_length = int(raw_content_length)
        except ValueError:
            return JSONResponse(status_code=400, content={"detail": "Invalid Content-Length."})
        if content_length > 1_048_576:
            return JSONResponse(status_code=413, content={"detail": "Request body is too large."})
    return await call_next(request)


@app.get("/health")
def health_check() -> dict[str, object]:
    return {
        "status": "ok",
        "app": settings.app_name,
        "environment": settings.environment,
    }


@app.get("/ready")
def readiness_check() -> dict[str, object]:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        logger.exception("Readiness check could not connect to the database")
        raise HTTPException(status_code=503, detail="Database is unavailable.") from exc
    return {"status": "ready"}


@app.get("/api/config/providers")
def provider_status() -> dict[str, object]:
    return {
        "providers": {
            "gemini": {"configured": bool(settings.gemini_api_key)},
            "openrouter": {"configured": bool(settings.openrouter_api_key)},
        },
        "judge_enabled": settings.judge_enabled,
        "judge_provider": settings.judge_provider,
        "environment": settings.environment,
    }


@app.get("/api/datasets")
def list_datasets() -> list[dict[str, object]]:
    available: list[dict[str, object]] = []
    if not DATASETS_DIR.is_dir():
        return available
    for path in sorted(DATASETS_DIR.iterdir(), key=lambda item: item.name.casefold()):
        if not path.is_file() or path.name.casefold() == "manifest.json":
            continue
        if path.suffix.casefold() not in {".csv", ".json"}:
            continue
        try:
            dataset = load_dataset(path)
        except DatasetValidationError:
            continue
        available.append(
            {
                "dataset_file": path.name,
                "dataset_name": dataset.dataset_name,
                "dataset_version": dataset.dataset_version,
                "case_count": len(dataset.cases),
                "sha256": dataset.source_sha256,
            }
        )
    return available


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


@app.post("/api/analyses/compare", response_model=RunAnalysisResponse, status_code=201)
def create_run_comparison(
    request: RunComparisonRequest,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    baseline = db.get(BenchmarkRun, request.baseline_run_id)
    candidate = db.get(BenchmarkRun, request.candidate_run_id)
    if baseline is None or candidate is None:
        raise HTTPException(status_code=404, detail="Baseline or candidate run was not found.")
    if baseline.status == "running" or candidate.status == "running":
        raise HTTPException(status_code=409, detail="Both runs must finish before comparison.")
    try:
        result = compare_runs(
            baseline,
            candidate,
            alpha=request.alpha,
            minimum_regression_drop=request.minimum_regression_drop,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not result.metrics:
        raise HTTPException(
            status_code=422,
            detail="The runs have no paired completed cases with comparable metrics.",
        )

    analysis = RunAnalysis(
        id=str(uuid.uuid4()),
        baseline_run_id=baseline.id,
        candidate_run_id=candidate.id,
        method_version=result.method_version,
        alpha=request.alpha,
        minimum_regression_drop=request.minimum_regression_drop,
        created_at=datetime.now(timezone.utc),
        result=result.model_dump(mode="json"),
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    return {
        "id": analysis.id,
        "created_at": analysis.created_at.isoformat(),
        "result": analysis.result,
    }


@app.get("/api/analyses", response_model=list[RunAnalysisListItem])
def list_run_analyses(
    limit: int = 50,
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    if not 1 <= limit <= 200:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 200")
    analyses = db.scalars(
        select(RunAnalysis).order_by(RunAnalysis.created_at.desc()).limit(limit)
    ).all()
    return [
        {
            "id": analysis.id,
            "created_at": analysis.created_at.isoformat(),
            "baseline_run_id": analysis.baseline_run_id,
            "candidate_run_id": analysis.candidate_run_id,
            "method_version": analysis.method_version,
            "metric_count": len(analysis.result.get("metrics", [])),
            "regressions_detected": sum(
                metric.get("regression_detected", False)
                for metric in analysis.result.get("metrics", [])
            ),
        }
        for analysis in analyses
    ]


@app.get("/api/analyses/{analysis_id}", response_model=RunAnalysisResponse)
def get_run_analysis(
    analysis_id: str,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    analysis = db.get(RunAnalysis, analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis was not found.")
    return {
        "id": analysis.id,
        "created_at": analysis.created_at.isoformat(),
        "result": analysis.result,
    }
