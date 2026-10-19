"""Database records for benchmark runs and per-case outputs."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class BenchmarkRun(Base):
    __tablename__ = "benchmark_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    dataset_file: Mapped[str] = mapped_column(String(255), nullable=False)
    dataset_name: Mapped[str] = mapped_column(String(255), nullable=False)
    dataset_version: Mapped[str] = mapped_column(String(100), nullable=False)
    dataset_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model_id: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    judge_enabled: Mapped[bool] = mapped_column(default=False, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    total_cases: Mapped[int] = mapped_column(Integer, nullable=False)
    completed_cases: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    passed_cases: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    errored_cases: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_input_tokens: Mapped[int | None] = mapped_column(Integer)
    total_output_tokens: Mapped[int | None] = mapped_column(Integer)
    total_latency_ms: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    total_estimated_cost_usd: Mapped[float | None] = mapped_column(Float)
    error_message: Mapped[str | None] = mapped_column(Text)

    cases: Mapped[list[BenchmarkCaseResult]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="BenchmarkCaseResult.ordinal"
    )

    __table_args__ = (Index("ix_benchmark_runs_started_at", "started_at"),)


class BenchmarkCaseResult(Base):
    __tablename__ = "benchmark_case_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("benchmark_runs.id", ondelete="CASCADE"), nullable=False
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    test_case_id: Mapped[str] = mapped_column(String(255), nullable=False)
    evaluation_method: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    candidate_text: Mapped[str | None] = mapped_column(Text)
    provider: Mapped[str | None] = mapped_column(String(50))
    model_id: Mapped[str | None] = mapped_column(String(255))
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[float | None] = mapped_column(Float)
    estimated_cost_usd: Mapped[float | None] = mapped_column(Float)
    deterministic_result: Mapped[dict | None] = mapped_column(JSON)
    semantic_result: Mapped[dict | None] = mapped_column(JSON)
    judge_result: Mapped[dict | None] = mapped_column(JSON)
    evaluation_error: Mapped[str | None] = mapped_column(Text)
    error_category: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(Text)

    run: Mapped[BenchmarkRun] = relationship(back_populates="cases")

    __table_args__ = (
        Index("ix_benchmark_case_results_run_case", "run_id", "test_case_id", unique=True),
    )
