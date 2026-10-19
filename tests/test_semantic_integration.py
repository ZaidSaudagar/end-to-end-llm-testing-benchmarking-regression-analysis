"""Opt-in smoke test using a tiny synthetic fixture and the configured real model."""

from __future__ import annotations

import os

import pytest
from backend.evaluation.semantic import SemanticScorer

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_REAL_EMBEDDING_TESTS") != "1",
    reason="set RUN_REAL_EMBEDDING_TESTS=1 to load the configured Sentence Transformers model",
)


def test_real_model_ranks_synthetic_paraphrase_above_unrelated_text() -> None:
    scorer = SemanticScorer()
    scores = scorer.score_batch(
        ["Paris is the capital of France.", "Paris is the capital of France."],
        [
            "France's capital city is Paris.",
            "A bicycle has two wheels and pedals.",
        ],
        test_case_ids=["SYN-PARAPHRASE", "SYN-UNRELATED"],
    )

    assert scores[0].similarity is not None
    assert scores[1].similarity is not None
    assert scores[0].similarity > scores[1].similarity
