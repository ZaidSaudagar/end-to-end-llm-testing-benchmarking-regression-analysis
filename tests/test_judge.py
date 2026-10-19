"""Credential-free tests for structured LLM judging and failure handling."""

import asyncio
import json

import pytest
from backend.config import Settings
from backend.evaluation.judge import JudgeRequest, LLMJudge, build_configured_judge
from backend.providers import GenerationRequest, MockProvider, ProviderError, ProviderResponse


def valid_json(score: int = 4, factual: int | None = 4) -> str:
    return json.dumps(
        {
            "relevance": {"score": score, "rationale": "Addresses the task."},
            "completeness": {"score": 4, "rationale": "Covers the key parts."},
            "instruction_following": {"score": 5, "rationale": "Follows the requested format."},
            "factual_alignment": {"score": factual, "rationale": "Matches supplied evidence."},
            "clarity": {"score": 4, "rationale": "Clear and readable."},
        }
    )


class SequenceProvider:
    provider_name = "sequence"

    def __init__(self, responses: list[str | Exception]) -> None:
        self.responses = responses
        self.requests: list[GenerationRequest] = []

    async def generate(self, request: GenerationRequest) -> ProviderResponse:
        self.requests.append(request)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return ProviderResponse(
            provider=self.provider_name,
            model_id="judge-v1",
            text=response,
            latency_ms=3,
        )


def req(**updates: object) -> JudgeRequest:
    values = {
        "prompt": "Answer the question using the context.",
        "candidate_answer": "A candidate answer.",
        "reference_context": "Relevant context.",
        "test_case_id": "case-1",
        "candidate_model_id": "candidate-secret-model-name",
    }
    values.update(updates)
    return JudgeRequest(**values)


def test_valid_response_records_metadata_and_blinds_candidate_identity() -> None:
    provider = MockProvider(valid_json(), model_id="judge-model")
    outcome = asyncio.run(LLMJudge(provider, "judge-model").evaluate(req()))
    assert outcome is not None
    assert outcome.status == "success"
    run = outcome.runs[0]
    assert run.overall_score == 4.2
    assert run.judge_provider == "mock"
    assert run.judge_model_id == "judge-model"
    assert run.prompt_version == "llm-judge-prompt-v1"
    assert run.rubric_version == "llm-judge-rubric-v1"
    assert "candidate-secret-model-name" not in provider.requests[0].prompt
    assert outcome.candidate_model_id == "candidate-secret-model-name"


def test_missing_reference_forces_factual_score_to_not_assessed() -> None:
    outcome = asyncio.run(
        LLMJudge(MockProvider(valid_json()), "judge-model").evaluate(req(reference_context=None))
    )
    assert outcome is not None
    factual = outcome.runs[0].scorecard.factual_alignment
    assert factual.score is None
    assert "No reference material" in factual.rationale
    assert outcome.runs[0].overall_score == 4.25


def test_invalid_response_gets_one_bounded_repair_attempt() -> None:
    provider = SequenceProvider(["not json", valid_json()])
    outcome = asyncio.run(LLMJudge(provider, "judge-model").evaluate(req()))
    assert outcome is not None
    assert outcome.status == "success"
    assert outcome.runs[0].attempt_count == 2
    assert len(provider.requests) == 2


def test_repeated_malformed_response_is_failure_not_zero() -> None:
    provider = SequenceProvider(["bad", "still bad"])
    outcome = asyncio.run(LLMJudge(provider, "judge-model").evaluate(req()))
    assert outcome is not None
    assert outcome.status == "failure"
    assert outcome.aggregate is None
    assert outcome.runs[0].scorecard is None
    assert outcome.runs[0].failure_category == "invalid_judge_response"
    assert outcome.runs[0].attempt_count == 2


def test_invalid_scores_fail_schema_validation() -> None:
    provider = SequenceProvider([valid_json(score=6), valid_json(score=6)])
    outcome = asyncio.run(LLMJudge(provider, "judge-model").evaluate(req()))
    assert outcome is not None
    assert outcome.status == "failure"
    assert outcome.runs[0].scorecard is None


def test_only_factual_alignment_can_be_unscored() -> None:
    provider = SequenceProvider(
        [
            valid_json().replace('"relevance": {"score": 4', '"relevance": {"score": null'),
            valid_json().replace('"relevance": {"score": 4', '"relevance": {"score": null'),
        ]
    )
    outcome = asyncio.run(LLMJudge(provider, "judge-model").evaluate(req()))
    assert outcome is not None
    assert outcome.status == "failure"
    assert outcome.runs[0].failure_category == "invalid_judge_response"


def test_provider_failure_is_recorded_without_retrying_as_a_response_error() -> None:
    provider = SequenceProvider([ProviderError("sequence", "rate_limited", "failed")])
    outcome = asyncio.run(LLMJudge(provider, "judge-model").evaluate(req()))
    assert outcome is not None
    assert outcome.status == "failure"
    assert outcome.runs[0].failure_category == "rate_limited"
    assert outcome.runs[0].attempt_count == 1


def test_disabled_judge_makes_no_provider_call() -> None:
    provider = MockProvider(valid_json())
    outcome = asyncio.run(LLMJudge(provider, "judge-model", enabled=False).evaluate(req()))
    assert outcome is None
    assert provider.requests == []


def test_repetitions_aggregate_only_successful_scores() -> None:
    provider = SequenceProvider([valid_json(score=3), valid_json(score=5), "bad", "bad"])
    outcome = asyncio.run(
        LLMJudge(provider, "judge-model", repetitions=3, max_response_attempts=1).evaluate(req())
    )
    assert outcome is not None
    assert outcome.status == "partial_failure"
    assert [run.status for run in outcome.runs] == ["success", "success", "failure"]
    assert outcome.aggregate.successful_repetitions == 2
    assert outcome.aggregate.failed_repetitions == 1
    assert outcome.aggregate.dimension_means["relevance"] == 4
    assert outcome.aggregate.overall_population_stddev is not None


def test_configured_judge_is_off_by_default_and_requires_selected_provider() -> None:
    assert build_configured_judge(Settings(judge_enabled=False)) is None
    config = Settings(judge_enabled=True, judge_provider="gemini")
    with pytest.raises(ValueError, match="no configured credentials"):
        build_configured_judge(config, providers={})


def test_attempt_and_repetition_limits_are_bounded() -> None:
    provider = MockProvider(valid_json())
    with pytest.raises(ValueError, match="max_response_attempts"):
        LLMJudge(provider, "judge-model", max_response_attempts=4)
    with pytest.raises(ValueError, match="repetitions"):
        LLMJudge(provider, "judge-model", repetitions=6)
