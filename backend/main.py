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
    CustomModelCreateRequest,
    CustomModelResponse,
    CustomModelTestRequest,
    CustomModelTestResponse,
    RunCreateRequest,
    RunDetailResponse,
    RunSummary,
)
from backend.evaluation.runner import execute_run
from backend.models import BenchmarkRun, CustomModel, RunAnalysis
from backend.providers import create_configured_providers
from backend.providers.factory import create_custom_provider
from backend.providers.models import GenerationRequest

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
def provider_status(db: Session = Depends(get_db)) -> dict[str, object]:
    custom_models = db.scalars(select(CustomModel).where(CustomModel.is_active)).all()
    return {
        "providers": {
            "gemini": {
                "name": "Google Gemini",
                "configured": bool(settings.gemini_api_key),
                "default_model": settings.gemini_model_id,
                "available_models": ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"],
            },
            "groq": {
                "name": "Groq Cloud (Free Tier)",
                "configured": bool(settings.groq_api_key),
                "default_model": settings.groq_model_id,
                "available_models": [
                    "llama-3.3-70b-versatile",
                    "llama-3.1-8b-instant",
                    "deepseek-r1-distill-llama-70b",
                    "gemma2-9b-it",
                ],
            },
            "minimax": {
                "name": "KiraAI MiniMax",
                "configured": bool(settings.minimax_api_key),
                "default_model": settings.minimax_model_id,
                "available_models": [settings.minimax_model_id],
            },
        },
        "custom_models": [
            {
                "id": m.id,
                "name": m.name,
                "model_id": m.model_id,
                "base_url": m.base_url,
                "has_api_key": bool(m.api_key),
            }
            for m in custom_models
        ],
        "judge_enabled": settings.judge_enabled,
        "judge_provider": settings.judge_provider,
        "environment": settings.environment,
    }


@app.get("/api/custom-models", response_model=list[CustomModelResponse])
def list_custom_models(db: Session = Depends(get_db)) -> list[CustomModelResponse]:
    models = db.scalars(select(CustomModel).order_by(CustomModel.created_at.desc())).all()
    return [
        CustomModelResponse(
            id=m.id,
            name=m.name,
            model_id=m.model_id,
            base_url=m.base_url,
            has_api_key=bool(m.api_key),
            description=m.description,
            created_at=m.created_at.isoformat(),
            is_active=m.is_active,
        )
        for m in models
    ]


@app.post("/api/custom-models", response_model=CustomModelResponse, status_code=201)
def create_custom_model(
    payload: CustomModelCreateRequest,
    db: Session = Depends(get_db),
) -> CustomModelResponse:
    custom_model = CustomModel(
        id=str(uuid.uuid4()),
        name=payload.name.strip(),
        model_id=payload.model_id.strip(),
        base_url=payload.base_url.strip(),
        api_key=payload.api_key.strip() if payload.api_key else None,
        description=payload.description.strip() if payload.description else None,
        created_at=datetime.now(timezone.utc),
        is_active=True,
    )
    db.add(custom_model)
    db.commit()
    db.refresh(custom_model)
    return CustomModelResponse(
        id=custom_model.id,
        name=custom_model.name,
        model_id=custom_model.model_id,
        base_url=custom_model.base_url,
        has_api_key=bool(custom_model.api_key),
        description=custom_model.description,
        created_at=custom_model.created_at.isoformat(),
        is_active=custom_model.is_active,
    )


@app.delete("/api/custom-models/{model_id}")
def delete_custom_model(model_id: str, db: Session = Depends(get_db)) -> dict[str, str]:
    record = db.scalar(select(CustomModel).where(CustomModel.id == model_id))
    if not record:
        raise HTTPException(status_code=404, detail="Custom model not found.")
    db.delete(record)
    db.commit()
    return {"status": "deleted", "id": model_id}


@app.post("/api/custom-models/test", response_model=CustomModelTestResponse)
async def test_custom_model(payload: CustomModelTestRequest) -> CustomModelTestResponse:
    provider = create_custom_provider(
        base_url=payload.base_url,
        api_key=payload.api_key or "",
        default_model_id=payload.model_id,
        name="test_probe",
    )
    try:
        response = await provider.generate(GenerationRequest(prompt=payload.prompt))
        return CustomModelTestResponse(
            success=True,
            latency_ms=response.latency_ms,
            reply=response.text[:200],
        )
    except Exception as exc:
        return CustomModelTestResponse(
            success=False,
            latency_ms=0.0,
            error=str(exc),
        )


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


@app.get("/api/datasets/{dataset_file}/cases")
def get_dataset_cases(dataset_file: str) -> dict[str, object]:
    dataset_path = DATASETS_DIR / dataset_file
    if not dataset_path.is_file():
        raise HTTPException(status_code=404, detail="Dataset file was not found.")
    try:
        dataset = load_dataset(dataset_path)
    except DatasetValidationError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid dataset: {exc}") from exc
    return {
        "dataset_file": dataset_file,
        "dataset_name": dataset.dataset_name,
        "dataset_version": dataset.dataset_version,
        "sha256": dataset.source_sha256,
        "total_cases": len(dataset.cases),
        "cases": [case.model_dump(mode="json") for case in dataset.cases],
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

    configured_providers = create_configured_providers()
    provider = configured_providers.get(request.provider)
    model_id = request.model_id

    if provider is None:
        # Check custom models from database
        custom_record = db.scalar(
            select(CustomModel).where(
                (CustomModel.id == request.provider)
                | (CustomModel.name == request.provider)
                | (CustomModel.model_id == request.provider)
            )
        )
        if custom_record:
            provider = create_custom_provider(
                base_url=custom_record.base_url,
                api_key=custom_record.api_key or "",
                default_model_id=custom_record.model_id,
                name=custom_record.name,
            )
            model_id = model_id or custom_record.model_id
        else:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Provider '{request.provider}' has no configured credentials "
                    "or registered model."
                ),
            )

    if not model_id:
        if request.provider == "gemini":
            model_id = settings.gemini_model_id
        elif request.provider == "groq":
            model_id = settings.groq_model_id
        elif request.provider == "minimax":
            model_id = settings.minimax_model_id
        else:
            model_id = "default"

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
