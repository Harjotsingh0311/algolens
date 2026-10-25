from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any, Protocol

from algolens.retrieval.bm25 import is_answer_eligible


class HybridSearch(Protocol):
    """Interface for the runtime hybrid retriever."""

    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        candidate_k: int | None = None,
    ) -> list[dict[str, Any]]:
        """Return hybrid-ranked candidate records."""
        ...


class Reranker(Protocol):
    """Interface for a query-passage reranker."""

    def rerank(
        self,
        query: str,
        candidates: Sequence[Mapping[str, Any]],
        *,
        top_k: int | None = None,
    ) -> list[dict[str, Any]]:
        """Return the highest-ranked candidates with rerank scores."""
        ...


class RetrievalPipeline:
    """Coordinate hybrid retrieval and cross-encoder reranking.

    The canonical hybrid results remain the source of truth for retrieval
    scores, citations, source metadata, and review status. Reranking only
    changes ordering and adds reranking metadata.

    This component retrieves evidence; it does not generate answers.
    """

    def __init__(
        self,
        *,
        hybrid_index: HybridSearch,
        reranker: Reranker,
        candidate_k: int = 20,
        include_unreviewed: bool = False,
    ) -> None:
        if candidate_k < 1:
            raise ValueError("candidate_k must be at least 1.")

        self.hybrid_index = hybrid_index
        self.reranker = reranker
        self.candidate_k = candidate_k
        self.include_unreviewed = include_unreviewed

    @staticmethod
    def _chunk_id(candidate: Mapping[str, Any], stage: str) -> str:
        chunk_id = str(candidate.get("chunk_id", "")).strip()
        if not chunk_id:
            raise ValueError(f"{stage} returned a candidate without chunk_id.")
        return chunk_id

    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """Retrieve candidates, enforce review gates, then rerank."""
        if top_k < 1:
            raise ValueError("top_k must be at least 1.")

        if not query.strip():
            return []

        # Retrieve a broader pool before reranking so relevant passages can
        # move upward even if their original hybrid position was lower.
        candidate_depth = max(self.candidate_k, top_k)
        retrieved = self.hybrid_index.search(
            query,
            top_k=candidate_depth,
            candidate_k=candidate_depth,
        )

        canonical_by_id: dict[str, dict[str, Any]] = {}
        eligible_candidates: list[dict[str, Any]] = []

        for original in retrieved:
            candidate = dict(original)
            chunk_id = self._chunk_id(candidate, "Hybrid retrieval")

            if chunk_id in canonical_by_id:
                raise ValueError(f"Duplicate chunk ID: {chunk_id}")

            canonical_by_id[chunk_id] = candidate

            if not self.include_unreviewed and not is_answer_eligible(candidate):
                continue

            eligible_candidates.append(candidate)

        if not eligible_candidates:
            return []

        reranked = self.reranker.rerank(
            query,
            eligible_candidates,
            top_k=top_k,
        )

        results: list[dict[str, Any]] = []
        seen_reranked_ids: set[str] = set()

        for rerank_position, scored_candidate in enumerate(reranked, start=1):
            chunk_id = self._chunk_id(scored_candidate, "Reranker")

            if chunk_id not in canonical_by_id:
                raise ValueError(f"Reranker returned unknown chunk ID: {chunk_id}")

            if chunk_id in seen_reranked_ids:
                raise ValueError(f"Reranker returned duplicate chunk ID: {chunk_id}")
            seen_reranked_ids.add(chunk_id)

            canonical = canonical_by_id[chunk_id]

            # A result cannot bypass the review gate, even in diagnostic mode.
            if not self.include_unreviewed and not is_answer_eligible(canonical):
                raise ValueError(f"Reranker returned ineligible chunk ID: {chunk_id}")

            raw_score = scored_candidate.get("rerank_score")
            if (
                isinstance(raw_score, bool)
                or not isinstance(raw_score, (int, float))
                or not math.isfinite(float(raw_score))
            ):
                raise ValueError(f"Reranker returned an invalid rerank score for {chunk_id}.")

            result = dict(canonical)
            result["rerank_score"] = float(raw_score)
            result["rerank_rank"] = rerank_position
            result["reranking_method"] = str(
                scored_candidate.get("reranking_method", "cross_encoder")
            )

            # Compute eligibility from canonical status, not a component's
            # potentially stale or incorrect eligible_for_answer field.
            result["eligible_for_answer"] = is_answer_eligible(result)
            results.append(result)

        return results
