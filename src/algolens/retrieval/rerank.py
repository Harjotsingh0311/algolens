from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

from algolens.retrieval.bm25 import is_answer_eligible

DEFAULT_CROSS_ENCODER_MODEL = "cross-encoder/ms-marco-MiniLM-L6-v2"


class CrossEncoderReranker:
    """Rerank retrieved passages by query-passage relevance.

    Cross-encoder scores are ranking scores, not probabilities. Existing
    retrieval scores, chunk text, citations, and source metadata are retained.
    The model is loaded lazily so tests and empty-corpus checks need no download.
    """

    def __init__(
        self,
        *,
        model_name: str = DEFAULT_CROSS_ENCODER_MODEL,
        device: str | None = None,
        encoder: Any | None = None,
        include_unreviewed: bool = False,
        batch_size: int = 16,
    ) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be at least 1.")

        self.model_name = model_name
        self.device = device
        self.encoder = encoder
        self.include_unreviewed = include_unreviewed
        self.batch_size = batch_size

    def _get_encoder(self) -> Any:
        """Load the optional Sentence Transformers CrossEncoder on demand."""
        if self.encoder is None:
            try:
                from sentence_transformers import CrossEncoder
            except ImportError as exc:
                raise RuntimeError(
                    "Cross-encoder reranking requires the optional semantic "
                    "dependencies. Install the project with its semantic extra."
                ) from exc

            kwargs: dict[str, Any] = {}
            if self.device is not None:
                kwargs["device"] = self.device

            self.encoder = CrossEncoder(self.model_name, **kwargs)

        return self.encoder

    @staticmethod
    def _scores_to_list(raw_scores: Any, expected_count: int) -> list[float]:
        """Validate the one-scalar-score-per-passage output contract."""
        if hasattr(raw_scores, "tolist"):
            raw_scores = raw_scores.tolist()

        if not isinstance(raw_scores, (list, tuple)):
            raise ValueError("Cross-encoder must return one score per candidate.")

        if len(raw_scores) != expected_count:
            raise ValueError(
                "Cross-encoder returned a different number of scores than the number of candidates."
            )

        scores: list[float] = []
        for value in raw_scores:
            # Some model wrappers return an (n, 1) array rather than (n,).
            if isinstance(value, (list, tuple)):
                if len(value) != 1:
                    raise ValueError("Cross-encoder must return one scalar score per candidate.")
                value = value[0]

            try:
                score = float(value)
            except (TypeError, ValueError) as exc:
                raise ValueError("Cross-encoder scores must be finite numbers.") from exc

            if not math.isfinite(score):
                raise ValueError("Cross-encoder scores must be finite numbers.")

            scores.append(score)

        return scores

    def rerank(
        self,
        query: str,
        candidates: Sequence[Mapping[str, Any]],
        *,
        top_k: int | None = None,
    ) -> list[dict[str, Any]]:
        """Return candidates sorted by cross-encoder score, highest first."""
        if top_k is not None and top_k < 1:
            raise ValueError("top_k must be at least 1 when provided.")

        if not query.strip() or not candidates:
            return []

        candidate_records: list[dict[str, Any]] = []
        seen_ids: set[str] = set()

        for original in candidates:
            candidate = dict(original)
            chunk_id = str(candidate.get("chunk_id", "")).strip()

            if not chunk_id:
                raise ValueError("Every candidate must have a nonempty chunk_id.")
            if chunk_id in seen_ids:
                raise ValueError(f"Duplicate chunk ID: {chunk_id}")
            seen_ids.add(chunk_id)

            # Diagnostic mode can inspect unreviewed material, but it never
            # changes is_answer_eligible() or promotes that material to evidence.
            if not self.include_unreviewed and not is_answer_eligible(candidate):
                continue

            passage = candidate.get("retrieval_text") or candidate.get("text") or ""
            if not isinstance(passage, str):
                raise ValueError(f"Candidate {chunk_id} has invalid passage text.")
            if not passage.strip():
                continue

            candidate_records.append(candidate)

        if not candidate_records:
            return []

        pairs: list[tuple[str, str]] = [
            (
                query,
                str(candidate.get("retrieval_text") or candidate.get("text") or ""),
            )
            for candidate in candidate_records
        ]

        encoder = self._get_encoder()
        raw_scores = encoder.predict(
            pairs,
            batch_size=self.batch_size,
            show_progress_bar=False,
        )
        scores = self._scores_to_list(raw_scores, len(candidate_records))

        scored = list(enumerate(zip(candidate_records, scores, strict=True)))
        scored.sort(key=lambda item: (-item[1][1], item[0]))

        results: list[dict[str, Any]] = []
        selected = scored if top_k is None else scored[:top_k]

        for rank, (_, (candidate, score)) in enumerate(selected, start=1):
            result = dict(candidate)
            result["rerank_score"] = score
            result["rerank_rank"] = rank
            result["reranking_method"] = "cross_encoder"
            result["eligible_for_answer"] = is_answer_eligible(result)
            results.append(result)

        return results
