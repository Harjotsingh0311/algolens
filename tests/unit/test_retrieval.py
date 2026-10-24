from __future__ import annotations

import pytest

from algolens.retrieval.bm25 import (
    BM25Index,
    is_answer_eligible,
    reciprocal_rank_fusion,
    tokenize,
)


def make_chunk(
    chunk_id: str,
    text: str,
    *,
    review_status: str = "reviewed",
    citation: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "chunk_id": chunk_id,
        "text": text,
        "retrieval_text": f"MIT 6.046J {text}",
        "review_status": review_status,
        "citation": citation or {"kind": "pdf_page", "display": "p. 4"},
        "source_id": "L06_TYPED_NOTES",
    }


def test_tokenize_normalizes_case_and_unicode() -> None:
    tokens = tokenize("Randomized QUICKSORT Θ(n log n)")

    assert "randomized" in tokens
    assert "quicksort" in tokens
    assert "θ" in tokens
    assert "log" in tokens


def test_bm25_ranks_relevant_quicksort_chunk_first() -> None:
    chunks = [
        make_chunk(
            "unrelated",
            "Matrix multiplication and binary vectors.",
        ),
        make_chunk(
            "quicksort",
            "Randomized Quicksort pivot partition expected running time.",
        ),
        make_chunk(
            "pivot",
            "Pivot selection and balanced partition.",
        ),
    ]

    results = BM25Index(chunks).search(
        "randomized quicksort expected running time",
        top_k=3,
    )

    assert results
    assert results[0]["chunk_id"] == "quicksort"
    assert results[0]["score"] > 0


def test_unreviewed_chunks_are_excluded_by_default() -> None:
    chunks = [
        make_chunk(
            "draft",
            "Quicksort expected running time.",
            review_status="unreviewed_extraction",
        ),
    ]

    index = BM25Index(chunks)
    assert index.document_count == 0
    assert index.search("Quicksort") == []


def test_diagnostic_search_never_marks_unreviewed_as_eligible() -> None:
    chunks = [
        make_chunk(
            "draft",
            "Quicksort expected running time.",
            review_status="unreviewed_extraction",
        ),
    ]

    results = BM25Index(
        chunks,
        include_unreviewed=True,
    ).search("Quicksort expected", top_k=3)

    assert len(results) == 1
    assert results[0]["chunk_id"] == "draft"
    assert results[0]["eligible_for_answer"] is False


def test_search_preserves_citation_metadata() -> None:
    citation = {
        "kind": "pdf_page",
        "display": "pp. 4–5",
        "page_start": 4,
        "page_end": 5,
    }
    chunks = [
        make_chunk(
            "equations",
            "Quicksort recurrence expected time.",
            citation=citation,
        ),
    ]

    result = BM25Index(chunks).search("Quicksort recurrence")[0]

    assert result["citation"] == citation
    assert result["review_status"] == "reviewed"
    assert result["eligible_for_answer"] is True


def test_empty_query_and_unmatched_query_return_no_results() -> None:
    index = BM25Index([make_chunk("a", "Quicksort partitions arrays.")])

    assert index.search(" !!! ") == []
    assert index.search("cryptography blockchain") == []


def test_duplicate_chunk_ids_are_rejected() -> None:
    chunks = [
        make_chunk("duplicate", "Quicksort."),
        make_chunk("duplicate", "Pivot selection."),
    ]

    with pytest.raises(ValueError, match="Duplicate chunk ID"):
        BM25Index(chunks)


def test_search_rejects_invalid_top_k() -> None:
    index = BM25Index([make_chunk("a", "Quicksort partitions arrays.")])

    with pytest.raises(ValueError, match="top_k"):
        index.search("Quicksort", top_k=0)


def test_review_eligibility_requires_explicit_approval() -> None:
    assert is_answer_eligible({"review_status": "reviewed"})
    assert is_answer_eligible({"review_status": "verified"})
    assert not is_answer_eligible({"review_status": "pending_spot_check"})
    assert not is_answer_eligible({"review_status": "unreviewed_extraction"})
    assert not is_answer_eligible({})


def test_reciprocal_rank_fusion_combines_rankings() -> None:
    fused = reciprocal_rank_fusion(
        [
            ["a", "b", "c"],
            ["b", "d", "a"],
        ],
    )

    assert fused[0]["chunk_id"] == "b"
    assert len(fused) == 4
    assert fused[0]["score"] > fused[-1]["score"]


def test_reciprocal_rank_fusion_handles_duplicates_and_limit() -> None:
    fused = reciprocal_rank_fusion(
        [
            ["a", "a", "b"],
            ["b", "c"],
        ],
        limit=2,
    )

    assert [item["chunk_id"] for item in fused] == ["b", "a"]
    assert len(fused) == 2


def test_reciprocal_rank_fusion_rejects_invalid_arguments() -> None:
    with pytest.raises(ValueError, match="k"):
        reciprocal_rank_fusion([["a"]], k=0)

    with pytest.raises(ValueError, match="limit"):
        reciprocal_rank_fusion([["a"]], limit=0)
