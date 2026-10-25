from __future__ import annotations

from typing import Any

import pytest

from algolens.answerability import AnswerabilityGate, decide


def make_hit(
    chunk_id: str,
    rerank_score: float,
    *,
    section: str = "Randomized Quicksort",
    citation: str = "p. 4",
    review_status: str = "reviewed",
    eligible_for_answer: bool = True,
    rrf_score: float = 100.0,
) -> dict[str, Any]:
    return {
        "chunk_id": chunk_id,
        "text": f"Evidence about {section}.",
        "retrieval_text": f"Evidence about {section}.",
        "review_status": review_status,
        "eligible_for_answer": eligible_for_answer,
        "rerank_score": rerank_score,
        "score": rrf_score,
        "reranking_method": "cross_encoder",
        "section_start": section,
        "sections": [section],
        "source_id": "L06_TYPED_NOTES",
        "citation": {"kind": "pdf_page", "display": citation},
    }


def test_empty_results_abstain() -> None:
    assessment = AnswerabilityGate().assess([])

    assert assessment.decision == "abstain"
    assert assessment.reason == "no_eligible_evidence"
    assert assessment.top_score is None
    assert assessment.closest_topics == ()
    assert decide([]) == "abstain"


def test_off_topic_low_score_abstains_and_reports_nearest_topics() -> None:
    hits = [
        make_hit(
            "weak",
            -0.8,
            section="Basic Quicksort Analysis",
            citation="p. 4",
        ),
        make_hit(
            "weaker",
            -1.2,
            section="Randomized Quicksort",
            citation="01:02:30",
        ),
    ]

    assessment = AnswerabilityGate().assess(hits)

    assert assessment.decision == "abstain"
    assert assessment.reason == "below_partial_threshold"
    assert assessment.closest_topics == (
        "Basic Quicksort Analysis (p. 4)",
        "Randomized Quicksort (01:02:30)",
    )


def test_near_miss_medium_score_returns_partial() -> None:
    hits = [
        make_hit(
            "near",
            0.6,
            section="Basic Quicksort Analysis",
            citation="p. 4",
        ),
        make_hit(
            "related",
            0.2,
            section="Randomized Quicksort",
            citation="p. 5",
        ),
    ]

    assessment = AnswerabilityGate().assess(hits)

    assert assessment.decision == "partial"
    assert assessment.reason == "partial_evidence"
    assert assessment.closest_topics[0] == "Basic Quicksort Analysis (p. 4)"


def test_strong_reranker_score_returns_answer() -> None:
    hits = [
        make_hit("strong", 2.2, section="Expected Running Time"),
        make_hit("support", 1.7, section="Recursion Tree"),
    ]

    assert AnswerabilityGate().assess(hits).decision == "answer"
    assert decide(hits) == "answer"


def test_unreviewed_hit_is_never_used_even_with_high_score() -> None:
    hits = [
        make_hit(
            "draft",
            100.0,
            review_status="pending_spot_check",
            eligible_for_answer=True,
        )
    ]

    assessment = AnswerabilityGate().assess(hits)

    assert assessment.decision == "abstain"
    assert assessment.reason == "no_eligible_evidence"
    assert assessment.top_score is None


def test_explicitly_ineligible_hit_is_ignored() -> None:
    hits = [
        make_hit(
            "blocked",
            100.0,
            review_status="reviewed",
            eligible_for_answer=False,
        ),
        make_hit("usable", 0.7, section="Partitioning"),
    ]

    assessment = AnswerabilityGate().assess(hits)

    assert assessment.decision == "partial"
    assert assessment.top_score == pytest.approx(0.7)
    assert assessment.closest_topics == ("Partitioning (p. 4)",)


def test_gate_uses_reranker_score_not_rrf_score() -> None:
    hit = make_hit("x", -0.5, rrf_score=999.0)

    assessment = AnswerabilityGate().assess([hit])

    assert assessment.decision == "abstain"
    assert assessment.top_score == pytest.approx(-0.5)


def test_assessment_exposes_margin_and_support_count() -> None:
    hits = [
        make_hit("a", 2.2, section="Expected Running Time"),
        make_hit("b", 1.6, section="Recursion Tree"),
        make_hit("c", 0.4, section="Partitioning"),
        make_hit("d", -0.2, section="Sorting"),
    ]

    assessment = AnswerabilityGate().assess(hits)

    assert assessment.top_score == pytest.approx(2.2)
    assert assessment.score_margin == pytest.approx(0.6)
    assert assessment.supporting_hit_count == 3
    assert assessment.thresholds_calibrated is False


def test_closest_topics_are_deduplicated() -> None:
    hits = [
        make_hit("a", 1.4, section="Randomized Quicksort", citation="p. 4"),
        make_hit("b", 0.9, section="Randomized Quicksort", citation="p. 4"),
        make_hit("c", 0.6, section="Basic Quicksort", citation="p. 3"),
    ]

    assessment = AnswerabilityGate().assess(hits)

    assert assessment.closest_topics == (
        "Randomized Quicksort (p. 4)",
        "Basic Quicksort (p. 3)",
    )


def test_contract_shaped_hit_uses_its_score_and_passage_metadata() -> None:
    hit = {
        "score": 2.1,
        "passage": {
            "id": "L06-T014-c2",
            "text": "The notes discuss randomized Quicksort.",
            "kind": "notes",
            "page": 4,
            "section": "Randomized Quicksort",
            "review_status": "reviewed",
            "eligible_for_answer": True,
        },
    }

    assessment = AnswerabilityGate().assess([hit])

    assert assessment.decision == "answer"
    assert assessment.top_score == pytest.approx(2.1)
    assert assessment.closest_topics == ("Randomized Quicksort (p. 4)",)


@pytest.mark.parametrize(
    "answer_threshold,partial_threshold",
    [
        (0.0, 0.0),
        (-1.0, 0.0),
    ],
)
def test_gate_rejects_invalid_threshold_order(
    answer_threshold: float,
    partial_threshold: float,
) -> None:
    with pytest.raises(ValueError, match="answer_threshold"):
        AnswerabilityGate(
            answer_threshold=answer_threshold,
            partial_threshold=partial_threshold,
        )


def test_gate_rejects_nonpositive_topic_limit() -> None:
    with pytest.raises(ValueError, match="closest_topics_k"):
        AnswerabilityGate(closest_topics_k=0)


@pytest.mark.parametrize("invalid_score", [float("nan"), float("inf"), float("-inf")])
def test_gate_rejects_nonfinite_scores(invalid_score: float) -> None:
    with pytest.raises(ValueError, match="finite"):
        AnswerabilityGate().assess([make_hit("invalid", invalid_score)])


def test_gate_rejects_missing_reranker_score() -> None:
    hit = make_hit("missing", 1.5)
    del hit["rerank_score"]

    with pytest.raises(ValueError, match="rerank_score"):
        AnswerabilityGate().assess([hit])


def test_gate_does_not_mutate_hits() -> None:
    hit = make_hit("stable", 2.0)
    original = dict(hit)
    original_citation = dict(hit["citation"])

    AnswerabilityGate().assess([hit])

    assert hit == original
    assert hit["citation"] == original_citation
