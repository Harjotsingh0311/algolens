from __future__ import annotations

from typing import Any

import pytest

from algolens.retrieval.pipeline import RetrievalPipeline


def make_candidate(
    chunk_id: str,
    text: str,
    *,
    review_status: str = "reviewed",
    score: float = 0.02,
) -> dict[str, Any]:
    return {
        "chunk_id": chunk_id,
        "text": text,
        "retrieval_text": text,
        "review_status": review_status,
        "eligible_for_answer": review_status in {"reviewed", "verified", "approved"},
        "citation": {"kind": "pdf_page", "display": f"p. {4 if chunk_id == 'a' else 5}"},
        "source_id": "L06_TYPED_NOTES",
        "source_sha256": "a" * 64,
        "score": score,
        "retrieval_method": "hybrid_rff",
    }


class FakeHybridIndex:
    def __init__(self, results: list[dict[str, Any]]) -> None:
        self.results = results
        self.calls: list[tuple[str, int, int]] = []

    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        candidate_k: int | None = None,
    ) -> list[dict[str, Any]]:
        depth = candidate_k if candidate_k is not None else top_k
        self.calls.append((query, top_k, depth))
        return self.results[:top_k]


class FakeReranker:
    def __init__(self, scores: dict[str, float]) -> None:
        self.scores = scores
        self.calls: list[tuple[str, list[str], int | None]] = []

    def rerank(self, query, candidates, *, top_k=None):
        self.calls.append((query, [candidate["chunk_id"] for candidate in candidates], top_k))
        ranked = sorted(
            candidates,
            key=lambda candidate: -self.scores[candidate["chunk_id"]],
        )
        results = []
        for rank, candidate in enumerate(ranked[:top_k], start=1):
            result = dict(candidate)
            result["rerank_score"] = self.scores[candidate["chunk_id"]]
            result["rerank_rank"] = rank
            result["reranking_method"] = "cross_encoder"
            results.append(result)
        return results


def test_pipeline_runs_hybrid_retrieval_then_reranking() -> None:
    candidates = [
        make_candidate("a", "Quicksort expected runtime.", score=0.04),
        make_candidate("b", "Quicksort recurrence.", score=0.03),
    ]
    hybrid = FakeHybridIndex(candidates)
    reranker = FakeReranker({"a": 0.2, "b": 3.1})

    pipeline = RetrievalPipeline(
        hybrid_index=hybrid,
        reranker=reranker,
        candidate_k=8,
    )
    results = pipeline.search("Explain the recurrence.", top_k=2)

    assert [item["chunk_id"] for item in results] == ["b", "a"]
    assert hybrid.calls == [("Explain the recurrence.", 8, 8)]
    assert reranker.calls == [("Explain the recurrence.", ["a", "b"], 2)]


def test_pipeline_preserves_citations_and_hybrid_scores() -> None:
    candidates = [
        make_candidate("a", "Quicksort expected runtime.", score=0.042),
        make_candidate("b", "Quicksort recurrence.", score=0.031),
    ]
    pipeline = RetrievalPipeline(
        hybrid_index=FakeHybridIndex(candidates),
        reranker=FakeReranker({"a": 0.5, "b": 2.0}),
    )

    results = pipeline.search("Explain Quicksort.")
    by_id = {item["chunk_id"]: item for item in results}

    assert by_id["a"]["citation"]["display"] == "p. 4"
    assert by_id["b"]["citation"]["display"] == "p. 5"
    assert by_id["a"]["score"] == 0.042
    assert by_id["b"]["score"] == 0.031
    assert by_id["b"]["rerank_score"] == 2.0
    assert by_id["b"]["source_sha256"] == "a" * 64
    assert by_id["b"]["eligible_for_answer"] is True


def test_pipeline_filters_unapproved_candidates_before_reranking() -> None:
    candidates = [
        make_candidate(
            "draft",
            "Unreviewed recurrence.",
            review_status="approved_retrieval_disabled",
        ),
        make_candidate("approved", "Reviewed recurrence."),
    ]
    reranker = FakeReranker({"draft": 10.0, "approved": 0.5})
    pipeline = RetrievalPipeline(
        hybrid_index=FakeHybridIndex(candidates),
        reranker=reranker,
    )

    results = pipeline.search("Explain the recurrence.")

    assert [item["chunk_id"] for item in results] == ["approved"]
    assert reranker.calls[0][1] == ["approved"]
    assert all(item["eligible_for_answer"] is True for item in results)


def test_diagnostic_mode_does_not_promote_unapproved_candidates() -> None:
    candidate = make_candidate(
        "draft",
        "Unreviewed recurrence.",
        review_status="approved_retrieval_disabled",
    )
    pipeline = RetrievalPipeline(
        hybrid_index=FakeHybridIndex([candidate]),
        reranker=FakeReranker({"draft": 10.0}),
        include_unreviewed=True,
    )

    results = pipeline.search("Explain the recurrence.")

    assert len(results) == 1
    assert results[0]["chunk_id"] == "draft"
    assert results[0]["eligible_for_answer"] is False


def test_pipeline_rejects_duplicate_hybrid_candidate_ids() -> None:
    duplicate = make_candidate("duplicate", "Quicksort recurrence.")
    pipeline = RetrievalPipeline(
        hybrid_index=FakeHybridIndex([duplicate, duplicate]),
        reranker=FakeReranker({"duplicate": 1.0}),
    )

    with pytest.raises(ValueError, match="Duplicate chunk ID"):
        pipeline.search("Explain Quicksort.")


def test_pipeline_rejects_unknown_reranker_result_ids() -> None:
    class UnknownIdReranker:
        def rerank(self, query, candidates, *, top_k=None):
            return [make_candidate("unknown", "Not from the candidate list.")]

    pipeline = RetrievalPipeline(
        hybrid_index=FakeHybridIndex([make_candidate("known", "Quicksort recurrence.")]),
        reranker=UnknownIdReranker(),
    )

    with pytest.raises(ValueError, match="unknown chunk ID"):
        pipeline.search("Explain Quicksort.")


def test_pipeline_rejects_invalid_top_k() -> None:
    pipeline = RetrievalPipeline(
        hybrid_index=FakeHybridIndex([]),
        reranker=FakeReranker({}),
    )

    with pytest.raises(ValueError, match="top_k"):
        pipeline.search("Explain Quicksort.", top_k=0)


def test_empty_query_skips_both_components() -> None:
    hybrid = FakeHybridIndex([])
    reranker = FakeReranker({})
    pipeline = RetrievalPipeline(
        hybrid_index=hybrid,
        reranker=reranker,
    )

    assert pipeline.search("   ") == []
    assert hybrid.calls == []
    assert reranker.calls == []
