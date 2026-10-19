"""Execute dataset cases against a provider and persist run/case records."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend.evaluation.datasets import DatasetDocument
from backend.evaluation.judge import JudgeRequest, LLMJudge
from backend.evaluation.metrics import evaluate_case
from backend.evaluation.semantic import SemanticScorer
from backend.models import BenchmarkCaseResult, BenchmarkRun
from backend.providers import GenerationRequest, Provider, ProviderError


def _sum_known(previous: int | float | None, current: int | float | None) -> int | float | None:
    if previous is None or current is None:
        return None
    return previous + current


async def execute_run(
    db: Session,
    *,
    dataset: DatasetDocument,
    dataset_file: str,
    provider_name: str,
    provider: Provider,
    model_id: str,
    judge: LLMJudge | None = None,
    semantic_scorer: SemanticScorer | None = None,
) -> BenchmarkRun:
    """Run cases in dataset order and commit each result for durable progress."""
    run = BenchmarkRun(
        id=str(uuid.uuid4()),
        dataset_file=dataset_file,
        dataset_name=dataset.dataset_name,
        dataset_version=dataset.dataset_version,
        dataset_sha256=dataset.source_sha256,
        provider=provider_name,
        model_id=model_id,
        status="running",
        judge_enabled=judge is not None,
        started_at=datetime.now(timezone.utc),
        total_cases=len(dataset.cases),
        completed_cases=0,
        passed_cases=0,
        errored_cases=0,
        total_input_tokens=0,
        total_output_tokens=0,
        total_latency_ms=0.0,
        total_estimated_cost_usd=0.0,
    )
    db.add(run)
    db.commit()

    for ordinal, case in enumerate(dataset.cases, start=1):
        record = BenchmarkCaseResult(
            id=str(uuid.uuid4()),
            run_id=run.id,
            ordinal=ordinal,
            test_case_id=case.test_case_id,
            evaluation_method=case.evaluation_method,
            status="error",
        )
        try:
            response = await provider.generate(
                GenerationRequest(prompt=case.input_prompt, model_id=model_id)
            )
            record.status = "completed"
            record.candidate_text = response.text
            record.provider = response.provider
            record.model_id = response.model_id
            record.input_tokens = response.usage.input_tokens
            record.output_tokens = response.usage.output_tokens
            record.latency_ms = response.latency_ms
            record.estimated_cost_usd = response.estimated_cost_usd
            try:
                if case.evaluation_method.casefold() == "semantic_similarity":
                    scorer = semantic_scorer or SemanticScorer()
                    semantic = scorer.score_batch(
                        [case.reference_answer],
                        [response.text],
                        test_case_ids=[case.test_case_id],
                    )[0]
                    record.semantic_result = semantic.model_dump(mode="json")
                else:
                    deterministic = evaluate_case(case, response.text)
                    record.deterministic_result = deterministic.model_dump(mode="json")
                    if deterministic.passed:
                        run.passed_cases += 1
            except (ValueError, TypeError) as exc:
                record.evaluation_error = str(exc)[:1000]

            if judge is not None:
                outcome = await judge.evaluate(
                    JudgeRequest(
                        prompt=case.input_prompt,
                        candidate_answer=response.text,
                        reference_answer=case.reference_answer,
                        reference_context=case.reference_context,
                        test_case_id=case.test_case_id,
                        candidate_model_id=response.model_id,
                    )
                )
                record.judge_result = outcome.model_dump(mode="json") if outcome else None

            run.total_input_tokens = _sum_known(run.total_input_tokens, response.usage.input_tokens)
            run.total_output_tokens = _sum_known(
                run.total_output_tokens, response.usage.output_tokens
            )
            run.total_latency_ms += response.latency_ms
            run.total_estimated_cost_usd = _sum_known(
                run.total_estimated_cost_usd, response.estimated_cost_usd
            )
            run.completed_cases += 1
        except ProviderError as exc:
            record.error_category = exc.error_type
            record.error_message = "Provider request failed."
            run.errored_cases += 1
        except Exception:
            record.error_category = "execution_error"
            record.error_message = "Case execution failed unexpectedly."
            run.errored_cases += 1

        db.add(record)
        db.commit()
        db.refresh(run)

    run.completed_at = datetime.now(timezone.utc)
    if run.errored_cases == run.total_cases:
        run.status = "failed"
        run.error_message = "All provider requests failed."
    elif run.errored_cases:
        run.status = "partial_failure"
    else:
        run.status = "completed"
    db.commit()
    db.refresh(run)
    return run
