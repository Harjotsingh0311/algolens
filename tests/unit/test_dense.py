from __future__ import annotations

import numpy as np
import pytest

from algolens.retrieval.dense import DenseIndex


class FakeEncoder:
    device = "cpu"

    @staticmethod
    def _vector(text: str) -> list[float]:
        normalized = text.casefold()
        return [
            float(normalized.count("quicksort")),
            float(normalized.count("partition")),
            float(normalized.count("matrix")),
            float(normalized.count("pivot")),
        ]

    def encode_document(self, sentences, **kwargs):
        return np.asarray(
            [self._vector(sentence) for sentence in sentences],
            dtype=np.float32,
        )

    def encode_query(self, sentences, **kwargs):
        return np.asarray(
            [self._vector(sentence) for sentence in sentences],
            dtype=np.float32,
        )


def make_chunk(
    chunk_id: str,
    text: str,
    *,
    review_status: str = "reviewed",
) -> dict[str, object]:
    return {
        "chunk_id": chunk_id,
        "parent_id": "parent-1",
        "text": text,
        "retrieval_text": text,
        "review_status": review_status,
        "citation": {"kind": "pdf_page", "display": "p. 4"},
        "source_id": "L06_TYPED_NOTES",
    }


def test_dense_search_ranks_semantically_matching_vector_first() -> None:
    chunks = [
        make_chunk("matrix", "Matrix multiplication."),
        make_chunk("quicksort", "Quicksort partition pivot."),
        make_chunk("partition", "Partition operation."),
    ]

    results = DenseIndex(chunks, encoder=FakeEncoder()).search(
        "Quicksort partition",
        top_k=3,
    )

    assert results[0]["chunk_id"] == "quicksort"
    assert results[0]["score"] > results[-1]["score"]
    assert results[0]["retrieval_method"] == "dense"


def test_dense_search_preserves_citation_and_review_gate() -> None:
    chunks = [
        make_chunk(
            "draft",
            "Quicksort partition pivot.",
            review_status="pending_spot_check",
        ),
    ]

    index = DenseIndex(chunks, encoder=FakeEncoder())
    assert index.search("Quicksort") == []

    diagnostic = DenseIndex(
        chunks,
        encoder=FakeEncoder(),
        include_unreviewed=True,
    ).search("Quicksort")

    assert diagnostic[0]["citation"]["display"] == "p. 4"
    assert diagnostic[0]["eligible_for_answer"] is False


def test_dense_empty_approved_corpus_does_not_load_model() -> None:
    chunks = [
        make_chunk(
            "draft",
            "Quicksort partition pivot.",
            review_status="unreviewed_extraction",
        ),
    ]

    index = DenseIndex(chunks)
    assert index.chunks == []
    assert index.search("Quicksort") == []
    assert index.device == "not-loaded"


def test_dense_search_rejects_invalid_top_k() -> None:
    index = DenseIndex(
        [make_chunk("a", "Quicksort partition pivot.")],
        encoder=FakeEncoder(),
    )

    with pytest.raises(ValueError, match="top_k"):
        index.search("Quicksort", top_k=0)


def test_dense_search_handles_empty_and_unmatched_queries() -> None:
    index = DenseIndex(
        [make_chunk("a", "Quicksort partition pivot.")],
        encoder=FakeEncoder(),
    )

    assert index.search("   ") == []
    # This fake encoder emits a zero vector for unmatched terms.
    # Zero-vector queries have no usable direction for cosine similarity.
    assert index.search("unrelated words") == []


def test_dense_index_rejects_duplicate_chunk_ids() -> None:
    chunks = [
        make_chunk("duplicate", "Quicksort pivot."),
        make_chunk("duplicate", "Matrix multiplication."),
    ]

    with pytest.raises(ValueError, match="Duplicate chunk ID"):
        DenseIndex(chunks, encoder=FakeEncoder())
