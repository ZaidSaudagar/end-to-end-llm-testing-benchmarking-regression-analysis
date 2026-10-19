from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.database import Base, engine

app = FastAPI(
    title="End-to-End LLM Testing, Benchmarking and Regression Analysis",
    version="0.1.0",
    description="Modular evaluation, benchmarking, and regression analysis backend.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
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
    return {
        "status": "ready",
        "database_url": settings.database_url,
        "debug": settings.debug,
    }


@app.get("/api/config/providers")
def provider_status() -> dict[str, object]:
    return {
        "providers": {
            "gemini": {"configured": bool(settings.app_name)},
            "openrouter": {"configured": False},
        },
        "environment": settings.environment,
    }


@app.get("/api/overview")
def overview() -> dict[str, object]:
    return {
        "project": settings.app_name,
        "status": "foundation_initialized",
        "metrics": {
            "total_runs": 0,
            "models_evaluated": 0,
            "test_cases_executed": 0,
        },
    }