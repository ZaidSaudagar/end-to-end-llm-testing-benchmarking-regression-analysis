"""Sentence Transformers based semantic similarity scoring."""

from __future__ import annotations

from functools import lru_cache
from importlib.metadata import PackageNotFoundError, version
from typing import Any, Callable, Sequence

import numpy as np

from backend.config import settings
from backend.evaluation.schemas import SemanticScore

ModelLoader = Callable[[str, str], Any]


@lru_cache(maxsize=2)
def _load_sentence_transformer(model_id: str, revision: str) -> Any:
    """Load each configured model revision once per process."""
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name_or_path=model_id, revision=revision)


def _library_version() -> str:
    try:
        return version("sentence-transformers")
    except PackageNotFoundError:
        return "unknown"


class SemanticScorer:
    """Batch scorer that records the encoder used and handles absent answers explicitly."""

    def __init__(
        self,
        model_id: str | None = None,
        model_revision: str | None = None,
        *,
        model_loader: ModelLoader = _load_sentence_transformer,
    ) -> None:
        self.model_id = model_id or settings.embedding_model_id
        self.model_revision = model_revision or settings.embedding_model_revision
        if not self.model_id.strip() or not self.model_revision.strip():
            raise ValueError("embedding model ID and revision must not be blank")
        self._model_loader = model_loader
        self.library_version = _library_version()

    def score_batch(
        self,
        references: Sequence[str | None],
        candidates: Sequence[str | None],
        *,
        test_case_ids: Sequence[str | None] | None = None,
        batch_size: int = 32,
    ) -> list[SemanticScore]:
        """Score aligned reference/candidate pairs; missing text receives no numeric score."""
        if len(references) != len(candidates):
            raise ValueError("references and candidates must have the same length")
        if batch_size < 1:
            raise ValueError("batch_size must be at least 1")
        if test_case_ids is not None and len(test_case_ids) != len(references):
            raise ValueError("test_case_ids must have the same length as references")

        ids = list(test_case_ids) if test_case_ids is not None else [None] * len(references)
        results: list[SemanticScore | None] = [None] * len(references)
        valid_indexes: list[int] = []
        texts: list[str] = []
        for index, (reference, candidate) in enumerate(zip(references, candidates, strict=True)):
            if not isinstance(reference, str) or not reference.strip():
                results[index] = self._missing_result(
                    ids[index], "No reference answer was provided."
                )
            elif not isinstance(candidate, str) or not candidate.strip():
                results[index] = self._missing_result(
                    ids[index], "No candidate answer was provided."
                )
            else:
                valid_indexes.append(index)
                texts.extend((reference, candidate))

        if valid_indexes:
            model = self._model_loader(self.model_id, self.model_revision)
            embeddings = np.asarray(
                model.encode(
                    texts,
                    batch_size=batch_size,
                    show_progress_bar=False,
                    convert_to_numpy=True,
                    normalize_embeddings=True,
                ),
                dtype=np.float64,
            )
            if embeddings.ndim == 1:
                embeddings = embeddings.reshape(1, -1)
            expected_rows = 2 * len(valid_indexes)
            if embeddings.ndim != 2 or embeddings.shape[0] != expected_rows:
                raise ValueError(
                    f"embedding model returned shape {embeddings.shape}; "
                    f"expected {expected_rows} rows"
                )
            if not np.isfinite(embeddings).all():
                raise ValueError("embedding model returned non-finite values")
            norms = np.linalg.norm(embeddings, axis=1)
            if np.any(norms == 0):
                raise ValueError("embedding model returned a zero-length vector")
            normalized = embeddings / norms[:, None]
            similarities = np.sum(normalized[0::2] * normalized[1::2], axis=1)
            for index, similarity in zip(valid_indexes, similarities, strict=True):
                results[index] = SemanticScore(
                    test_case_id=ids[index],
                    similarity=float(np.clip(similarity, -1.0, 1.0)),
                    model_id=self.model_id,
                    model_revision=self.model_revision,
                    embedding_library_version=self.library_version,
                    details=(
                        "Cosine similarity measures embedding proximity; it is not a "
                        "probability of factual correctness."
                    ),
                )

        return [result for result in results if result is not None]

    def _missing_result(self, test_case_id: str | None, details: str) -> SemanticScore:
        return SemanticScore(
            test_case_id=test_case_id,
            similarity=None,
            model_id=self.model_id,
            model_revision=self.model_revision,
            embedding_library_version=self.library_version,
            details=details,
        )
