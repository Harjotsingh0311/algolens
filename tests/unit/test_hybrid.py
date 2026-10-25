from __future__ import annotations

from typing import Any

import pytest

from algolens.retrieval.hybrid import HybridIndex


def make_chunk(
    chunk_id: str,
    text: str,
    *,
    review_status: str = "reviewed",
) -> dict[str, Any]:
    return {
        "chunk_id": chunk_id,
        "text": text,
        "retrieval_text": f"MIT 6.046J {text}",
        "review_status": review_status,
        "source_id": "L06_TYPED_NOTES",
        "citation": {
            "kind": "pdf_page",
            "display": f"p. {4 if chunk_id != 'b' else 5}",
        },
    }


class FakeIndex:
    """Deterministic stand-in for BM25Index or DenseIndex."""

    def __init__(self, results: list[dict[str, Any]]) -> None:
        self.results = results
        self.queries: list[tuple[str, int]] = []

    def search(self, query: str, *, top_k: int = 5) -> list[dict[str, Any]]:
        self.queries.append((query, top_k))
        return self.results[:top_k]


def sample_indexes() -> tuple[list[dict[str, Any]], FakeIndex, FakeIndex]:
    chunks = [
        make_chunk("a", "Quicksort expected running time."),
        make_chunk("b", "Quicksort recurrence and pivot selection."),
        make_chunk("c", "Partition cost."),
        make_chunk("d", "Randomized algorithms."),
    ]

    bm25 = FakeIndex(
        [
            chunks[0],
            chunks[1],
            chunks[2],
        ]
    )
    dense = FakeIndex(
        [
            chunks[1],
            chunks[3],
            chunks[0],
        ]
    )
    return chunks, bm25, dense


def test_hybrid_fuses_bm25_and_dense_rankings() -> None:
    chunks, bm25, dense = sample_indexes()
    index = HybridIndex(chunks, bm25_index=bm25, dense_index=dense)

    results = index.search("Quicksort expected time", top_k=4)

    assert [result["chunk_id"] for result in results] == [
        "b",
        "a",
        "d",
        "c",
    ]
    assert all(result["retrieval_method"] == "hybrid_rff" for result in results)
    assert results[0]["score"] > results[-1]["score"]


def test_hybrid_preserves_citations_and_source_metadata() -> None:
    chunks, bm25, dense = sample_indexes()
    index = HybridIndex(chunks, bm25_index=bm25, dense_index=dense)

    results = index.search("Quicksort recurrence", top_k=4)
    by_id = {result["chunk_id"]: result for result in results}

    assert by_id["b"]["citation"]["display"] == "p. 5"
    assert by_id["b"]["source_id"] == "L06_TYPED_NOTES"
    assert by_id["b"]["review_status"] == "reviewed"
    assert by_id["b"]["eligible_for_answer"] is True


def test_hybrid_uses_candidate_depth_before_truncating_results() -> None:
    chunks, bm25, dense = sample_indexes()
    index = HybridIndex(chunks, bm25_index=bm25, dense_index=dense)

    results = index.search(
        "Quicksort",
        top_k=2,
        candidate_k=3,
    )

    assert len(results) == 2
    assert bm25.queries == [("Quicksort", 3)]
    assert dense.queries == [("Quicksort", 3)]


def test_unapproved_chunks_are_excluded_by_default() -> None:
    approved = make_chunk("approved", "Quicksort recurrence.")
    draft = make_chunk(
        "draft",
        "Quicksort recurrence with an unreviewed formula.",
        review_status="approved_retrieval_disabled",
    )
    bm25 = FakeIndex([draft, approved])
    dense = FakeIndex([draft, approved])

    index = HybridIndex([approved, draft], bm25_index=bm25, dense_index=dense)
    results = index.search("Quicksort recurrence", top_k=5)

    assert [result["chunk_id"] for result in results] == ["approved"]
    assert all(result["eligible_for_answer"] is True for result in results)


def test_diagnostic_mode_never_marks_draft_as_eligible() -> None:
    approved = make_chunk("approved", "Quicksort recurrence.")
    draft = make_chunk(
        "draft",
        "Quicksort recurrence with an unreviewed formula.",
        review_status="approved_retrieval_disabled",
    )
    bm25 = FakeIndex([draft, approved])
    dense = FakeIndex([draft, approved])

    index = HybridIndex(
        [approved, draft],
        bm25_index=bm25,
        dense_index=dense,
        include_unreviewed=True,
    )
    results = index.search("Quicksort recurrence", top_k=5)
    by_id = {result["chunk_id"]: result for result in results}

    assert set(by_id) == {"approved", "draft"}
    assert by_id["approved"]["eligible_for_answer"] is True
    assert by_id["draft"]["eligible_for_answer"] is False


def test_hybrid_rejects_duplicate_chunk_ids() -> None:
    duplicate_chunks = [
        make_chunk("duplicate", "Quicksort recurrence."),
        make_chunk("duplicate", "Different passage."),
    ]

    with pytest.raises(ValueError, match="Duplicate chunk ID"):
        HybridIndex(
            duplicate_chunks,
            bm25_index=FakeIndex([]),
            dense_index=FakeIndex([]),
        )


def test_hybrid_rejects_invalid_top_k_and_candidate_depth() -> None:
    chunks, bm25, dense = sample_indexes()
    index = HybridIndex(chunks, bm25_index=bm25, dense_index=dense)

    with pytest.raises(ValueError, match="top_k"):
        index.search("Quicksort", top_k=0)

    with pytest.raises(ValueError, match="candidate_k"):
        index.search("Quicksort", top_k=3, candidate_k=2)


def test_hybrid_empty_query_returns_no_results() -> None:
    chunks, bm25, dense = sample_indexes()
    index = HybridIndex(chunks, bm25_index=bm25, dense_index=dense)

    assert index.search("   ") == []
    assert bm25.queries == []
    assert dense.queries == []
