from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol

from algolens.retrieval.bm25 import (
    BM25Index,
    is_answer_eligible,
    reciprocal_rank_fusion,
)
from algolens.retrieval.dense import DenseIndex


class SearchIndex(Protocol):
    """Shared interface for lexical and dense retrieval indexes."""

    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """Return ranked chunk records with provenance."""
        ...


class HybridIndex:
    """Combine BM25 and dense rankings with reciprocal rank fusion.

    The original chunk records remain the source of truth for citations and
    provenance. Component retrievers contribute ranked IDs, not replacement
    metadata. Unapproved chunks are excluded unless diagnostic mode is enabled.
    """

    def __init__(
        self,
        chunks: Sequence[Mapping[str, Any]],
        *,
        bm25_index: SearchIndex | None = None,
        dense_index: SearchIndex | None = None,
        include_unreviewed: bool = False,
        rrf_k: int = 60,
    ) -> None:
        if rrf_k < 1:
            raise ValueError("rrf_k must be at least 1.")

        self.include_unreviewed = include_unreviewed
        self.rrf_k = rrf_k
        self.chunks_by_id: dict[str, dict[str, Any]] = {}

        for original in chunks:
            chunk = dict(original)
            chunk_id = str(chunk.get("chunk_id", "")).strip()

            if not chunk_id:
                raise ValueError("Every chunk must have a nonempty chunk_id.")
            if chunk_id in self.chunks_by_id:
                raise ValueError(f"Duplicate chunk ID: {chunk_id}")

            self.chunks_by_id[chunk_id] = chunk

        # Production indexes use the same eligibility policy by default.
        # Injected indexes are supported for tests and specialized deployments.
        self.bm25_index = (
            bm25_index
            if bm25_index is not None
            else BM25Index(chunks, include_unreviewed=include_unreviewed)
        )
        self.dense_index = (
            dense_index
            if dense_index is not None
            else DenseIndex(chunks, include_unreviewed=include_unreviewed)
        )

    def _eligible_ranking(
        self,
        results: Sequence[Mapping[str, Any]],
        *,
        retriever_name: str,
    ) -> list[str]:
        """Validate retrieved IDs and enforce the canonical eligibility gate."""
        ranked_ids: list[str] = []

        for result in results:
            chunk_id = str(result.get("chunk_id", "")).strip()
            if not chunk_id:
                raise ValueError(f"{retriever_name} returned a result without chunk_id.")

            if chunk_id not in self.chunks_by_id:
                raise ValueError(f"{retriever_name} returned unknown chunk ID: {chunk_id}")

            source_chunk = self.chunks_by_id[chunk_id]
            if self.include_unreviewed or is_answer_eligible(source_chunk):
                ranked_ids.append(chunk_id)

        return ranked_ids

    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        candidate_k: int | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieve from both indexes, fuse ranks, then return the top results."""
        if top_k < 1:
            raise ValueError("top_k must be at least 1.")

        if candidate_k is None:
            candidate_depth = max(top_k, 10)
        else:
            if candidate_k < top_k:
                raise ValueError("candidate_k must be at least top_k.")
            candidate_depth = candidate_k

        if not query.strip():
            return []

        bm25_found = self.bm25_index.search(query, top_k=candidate_depth)
        dense_found = self.dense_index.search(query, top_k=candidate_depth)

        bm25_ids = self._eligible_ranking(
            bm25_found,
            retriever_name="BM25",
        )
        dense_ids = self._eligible_ranking(
            dense_found,
            retriever_name="Dense",
        )

        fused = reciprocal_rank_fusion(
            [bm25_ids, dense_ids],
            k=self.rrf_k,
        )

        results: list[dict[str, Any]] = []
        for item in fused[:top_k]:
            chunk_id = str(item["chunk_id"])
            # Preserve metadata from the canonical corpus, not a component
            # retriever's potentially incomplete result record.
            result = dict(self.chunks_by_id[chunk_id])
            result["score"] = float(item["score"])
            result["eligible_for_answer"] = is_answer_eligible(result)
            result["retrieval_method"] = "hybrid_rff"
            results.append(result)

        return results
