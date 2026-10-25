from __future__ import annotations

from typing import Any

import numpy as np
import pytest

from algolens.retrieval.rerank import CrossEncoderReranker


def make_candidate(
    chunk_id: str,
    text: str,
    *,
    review_status: str = "reviewed",
    score: float = 0.01,
) -> dict[str, Any]:
    return {
        "chunk_id": chunk_id,
        "text": text,
        "retrieval_text": text,
        "review_status": review_status,
        "eligible_for_answer": review_status in {"reviewed", "verified", "approved"},
        "citation": {
            "kind": "pdf_page",
            "display": f"p. {4 if chunk_id != 'b' else 5}",
        },
        "source_id": "L06_TYPED_NOTES",
        "score": score,
        "retrieval_method": "hybrid_rff",
    }


class FakeCrossEncoder:
    def __init__(self, scores: dict[str, float]) -> None:
        self.scores = scores
        self.calls: list[tuple[str, list[tuple[str, str]], dict[str, Any]]] = []

    def predict(self, pairs, **kwargs):
        materialized = list(pairs)
        self.calls.append(("predict", materialized, kwargs))
        return np.asarray(
            [self.scores[passage] for _, passage in materialized],
            dtype=np.float32,
        )


def test_reranker_sorts_by_cross_encoder_score_descending() -> None:
    candidates = [
        make_candidate("a", "Low relevance passage.", score=0.04),
        make_candidate("b", "Strongly relevant passage.", score=0.03),
        make_candidate("c", "Moderately relevant passage.", score=0.02),
    ]
    model = FakeCrossEncoder(
        {
            "Low relevance passage.": -1.5,
            "Strongly relevant passage.": 4.2,
            "Moderately relevant passage.": 0.3,
        }
    )

    results = CrossEncoderReranker(encoder=model).rerank(
        "Explain Quicksort",
        candidates,
    )

    assert [item["chunk_id"] for item in results] == ["b", "c", "a"]
    assert [item["rerank_rank"] for item in results] == [1, 2, 3]
    assert [item["rerank_score"] for item in results] == pytest.approx([4.2, 0.3, -1.5])


def test_reranker_preserves_citations_and_original_retrieval_score() -> None:
    candidate = make_candidate(
        "b",
        "Quicksort recurrence.",
        score=0.045,
    )
    model = FakeCrossEncoder({"Quicksort recurrence.": 2.4})

    result = CrossEncoderReranker(encoder=model).rerank(
        "Explain the recurrence",
        [candidate],
    )[0]

    assert result["citation"] == candidate["citation"]
    assert result["source_id"] == "L06_TYPED_NOTES"
    assert result["score"] == 0.045
    assert result["retrieval_method"] == "hybrid_rff"
    assert result["reranking_method"] == "cross_encoder"
    assert result["eligible_for_answer"] is True


def test_reranker_excludes_unapproved_candidates_by_default() -> None:
    candidates = [
        make_candidate(
            "draft",
            "Draft formula.",
            review_status="approved_retrieval_disabled",
        ),
        make_candidate("approved", "Reviewed formula."),
    ]
    model = FakeCrossEncoder(
        {
            "Draft formula.": 10.0,
            "Reviewed formula.": 0.5,
        }
    )

    results = CrossEncoderReranker(encoder=model).rerank(
        "Check the formula",
        candidates,
    )

    assert [item["chunk_id"] for item in results] == ["approved"]
    assert len(model.calls[0][1]) == 1
    assert results[0]["eligible_for_answer"] is True


def test_diagnostic_mode_never_promotes_unapproved_candidates() -> None:
    candidates = [
        make_candidate(
            "draft",
            "Draft formula.",
            review_status="approved_retrieval_disabled",
        ),
    ]
    model = FakeCrossEncoder({"Draft formula.": 9.0})

    results = CrossEncoderReranker(
        encoder=model,
        include_unreviewed=True,
    ).rerank("Check the formula", candidates)

    assert len(results) == 1
    assert results[0]["chunk_id"] == "draft"
    assert results[0]["eligible_for_answer"] is False


def test_empty_query_or_candidates_do_not_load_model() -> None:
    reranker = CrossEncoderReranker()

    assert reranker.rerank("Explain Quicksort", []) == []
    assert reranker.rerank("   ", [make_candidate("a", "A passage.")]) == []


def test_reranker_rejects_invalid_top_k() -> None:
    reranker = CrossEncoderReranker(encoder=FakeCrossEncoder({"A passage.": 1.0}))

    with pytest.raises(ValueError, match="top_k"):
        reranker.rerank(
            "Explain Quicksort",
            [make_candidate("a", "A passage.")],
            top_k=0,
        )


def test_reranker_rejects_duplicate_candidate_ids() -> None:
    candidates = [
        make_candidate("duplicate", "First passage."),
        make_candidate("duplicate", "Second passage."),
    ]

    with pytest.raises(ValueError, match="Duplicate chunk ID"):
        CrossEncoderReranker(
            encoder=FakeCrossEncoder(
                {
                    "First passage.": 1.0,
                    "Second passage.": 0.0,
                }
            )
        ).rerank("Explain Quicksort", candidates)


def test_reranker_rejects_non_finite_scores() -> None:
    class NonFiniteEncoder:
        def predict(self, pairs, **kwargs):
            return np.asarray([np.nan] * len(pairs))

    with pytest.raises(ValueError, match="finite"):
        CrossEncoderReranker(encoder=NonFiniteEncoder()).rerank(
            "Explain Quicksort",
            [make_candidate("a", "A passage.")],
        )


def test_reranker_rejects_wrong_number_of_scores() -> None:
    class WrongLengthEncoder:
        def predict(self, pairs, **kwargs):
            return np.asarray([1.0])

    candidates = [
        make_candidate("a", "First passage."),
        make_candidate("b", "Second passage."),
    ]

    with pytest.raises(ValueError, match="number of candidates"):
        CrossEncoderReranker(encoder=WrongLengthEncoder()).rerank(
            "Explain Quicksort",
            candidates,
        )


def test_reranker_applies_top_k_after_ranking() -> None:
    candidates = [
        make_candidate("a", "First passage."),
        make_candidate("b", "Second passage."),
        make_candidate("c", "Third passage."),
    ]
    model = FakeCrossEncoder(
        {
            "First passage.": 0.2,
            "Second passage.": 0.9,
            "Third passage.": 0.4,
        }
    )

    results = CrossEncoderReranker(encoder=model).rerank(
        "Explain Quicksort",
        candidates,
        top_k=2,
    )

    assert [item["chunk_id"] for item in results] == ["b", "c"]
