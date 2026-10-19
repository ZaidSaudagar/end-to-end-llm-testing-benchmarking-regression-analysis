from __future__ import annotations

from typing import Any

import numpy as np
import pytest
from backend.evaluation.semantic import SemanticScorer


class FakeEncoder:
    def __init__(self, vectors: dict[str, list[float]]) -> None:
        self.vectors = vectors
        self.calls: list[tuple[list[str], dict[str, Any]]] = []

    def encode(self, texts: list[str], **kwargs: Any) -> np.ndarray:
        self.calls.append((texts, kwargs))
        return np.asarray([self.vectors[text] for text in texts], dtype=np.float32)


def test_semantic_scoring_batches_pairs_and_preserves_alignment() -> None:
    encoder = FakeEncoder(
        {
            "paraphrase reference": [1.0, 0.0],
            "paraphrase candidate": [0.8, 0.6],
            "second reference": [0.0, 1.0],
            "unrelated candidate": [1.0, 0.0],
        }
    )
    scorer = SemanticScorer(
        model_id="fixture/model",
        model_revision="fixture-v1",
        model_loader=lambda model_id, revision: encoder,
    )

    results = scorer.score_batch(
        ["paraphrase reference", "second reference", None],
        ["paraphrase candidate", "unrelated candidate", "answer"],
        test_case_ids=["T-1", "T-2", "T-3"],
        batch_size=7,
    )

    assert [result.test_case_id for result in results] == ["T-1", "T-2", "T-3"]
    assert results[0].similarity == pytest.approx(0.8)
    assert results[1].similarity == pytest.approx(0.0)
    assert results[2].similarity is None
    assert results[0].model_id == "fixture/model"
    assert results[0].model_revision == "fixture-v1"
    assert "not a" in results[0].details
    assert len(encoder.calls) == 1
    assert encoder.calls[0][0] == [
        "paraphrase reference",
        "paraphrase candidate",
        "second reference",
        "unrelated candidate",
    ]
    assert encoder.calls[0][1]["batch_size"] == 7
    assert encoder.calls[0][1]["normalize_embeddings"] is True


def test_missing_answers_do_not_load_the_embedding_model() -> None:
    def fail_if_loaded(model_id: str, revision: str) -> Any:
        raise AssertionError("model must not load when every pair is missing")

    scorer = SemanticScorer(model_loader=fail_if_loaded)

    results = scorer.score_batch([None, "reference"], ["answer", "  "])

    assert [result.similarity for result in results] == [None, None]
    assert "No reference" in results[0].details
    assert "No candidate" in results[1].details


def test_semantic_scorer_validates_input_lengths_and_batch_size() -> None:
    scorer = SemanticScorer(model_loader=lambda model_id, revision: None)

    with pytest.raises(ValueError, match="same length"):
        scorer.score_batch(["one"], ["one", "two"])
    with pytest.raises(ValueError, match="batch_size"):
        scorer.score_batch(["one"], ["one"], batch_size=0)
    with pytest.raises(ValueError, match="test_case_ids"):
        scorer.score_batch(["one"], ["one"], test_case_ids=[])


def test_semantic_scorer_rejects_invalid_embedding_shapes() -> None:
    class InvalidEncoder:
        def encode(self, texts: list[str], **kwargs: Any) -> np.ndarray:
            return np.ones((1, 3), dtype=np.float32)

    scorer = SemanticScorer(model_loader=lambda model_id, revision: InvalidEncoder())

    with pytest.raises(ValueError, match="expected 2 rows"):
        scorer.score_batch(["reference"], ["candidate"])
