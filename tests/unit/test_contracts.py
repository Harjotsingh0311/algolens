from __future__ import annotations

import pytest
from pydantic import ValidationError

from algolens.answerability import AnswerabilityGate
from algolens.contracts import Answer, CitationReference, Claim, Hit, Passage


def approved_passage(**overrides: object) -> Passage:
    values: dict[str, object] = {
        "id": "passage-001",
        "lecture": 6,
        "kind": "notes",
        "text": "Randomized Quicksort chooses a pivot at random.",
        "t_start": None,
        "t_end": None,
        "page": 5,
        "section": "Randomized Quicksort",
        "parent_id": "parent-001",
        "pair_id": None,
        "citation": CitationReference(
            kind="pdf_page",
            display="p. 5",
            page_start=5,
            page_end=5,
        ),
        "source_id": "L06_TYPED_NOTES",
        "source_url": None,
        "source_sha256": "a" * 64,
        "review_status": "reviewed",
        "eligible_for_answer": True,
    }
    values.update(overrides)
    return Passage.model_validate(values)


def valid_answer(**overrides: object) -> Answer:
    passage = approved_passage()
    values: dict[str, object] = {
        "status": "answered",
        "answer_md": "Randomized Quicksort chooses a pivot at random.",
        "claims": [
            Claim(
                text="Randomized Quicksort chooses a pivot at random.",
                cites=[passage.id],
                support="supported",
            )
        ],
        "sources": [Hit(passage=passage, score=2.5, ranks={"hybrid": 1})],
        "closest_topics": [],
        "corpus_version": "test-corpus-v1",
        "model": "test-provider",
        "latency_ms": 12.5,
    }
    values.update(overrides)
    return Answer.model_validate(values)


def test_valid_notes_passage_preserves_page_citation() -> None:
    passage = approved_passage()
    assert passage.page == 5
    assert passage.citation is not None
    assert passage.citation.display == "p. 5"
    assert passage.eligible_for_answer is True


def test_spoken_passage_requires_ordered_timestamps() -> None:
    with pytest.raises(ValidationError):
        Passage(
            id="video-001",
            lecture=6,
            kind="spoken",
            text="The pivot is selected randomly.",
            section="Randomized Quicksort",
            t_start=None,
            t_end=None,
            review_status="reviewed",
            eligible_for_answer=True,
        )


def test_spoken_passage_rejects_end_before_start() -> None:
    with pytest.raises(ValidationError):
        Passage(
            id="video-001",
            lecture=6,
            kind="spoken",
            text="The pivot is selected randomly.",
            section="Randomized Quicksort",
            t_start=12.0,
            t_end=10.0,
            review_status="reviewed",
            eligible_for_answer=True,
        )


def test_ineligible_is_the_default_for_passages() -> None:
    passage = Passage(
        id="candidate-001",
        lecture=6,
        kind="notes",
        text="Candidate text.",
        section="Unreviewed",
    )
    assert passage.eligible_for_answer is False


def test_passage_cannot_claim_eligibility_without_approved_status() -> None:
    with pytest.raises(ValidationError):
        approved_passage(
            review_status="candidate_review_pending",
            eligible_for_answer=True,
        )


def test_explicit_ineligibility_overrides_approved_status() -> None:
    passage = approved_passage(eligible_for_answer=False)
    assert passage.eligible_for_answer is False


def test_pdf_citation_requires_page_metadata() -> None:
    with pytest.raises(ValidationError):
        CitationReference(kind="pdf_page", display="notes")


def test_video_citation_requires_valid_timestamp_range() -> None:
    with pytest.raises(ValidationError):
        CitationReference(
            kind="video_timestamp",
            display="00:15-00:10",
            start_seconds=15,
            end_seconds=10,
        )


def test_hit_rejects_non_finite_score() -> None:
    with pytest.raises(ValidationError):
        Hit(passage=approved_passage(), score=float("nan"))


def test_hit_rejects_invalid_rank() -> None:
    with pytest.raises(ValidationError):
        Hit(
            passage=approved_passage(),
            score=1.0,
            ranks={"hybrid": 0},
        )


def test_supported_claim_requires_citation() -> None:
    with pytest.raises(ValidationError):
        Claim(
            text="Randomized Quicksort picks a pivot at random.",
            cites=[],
            support="supported",
        )


def test_claim_rejects_duplicate_citation_ids() -> None:
    with pytest.raises(ValidationError):
        Claim(
            text="A claim.",
            cites=["passage-001", "passage-001"],
            support="supported",
        )


def test_answer_accepts_citation_to_retrieved_source() -> None:
    answer = valid_answer()
    assert answer.status == "answered"
    assert answer.claims[0].cites == ["passage-001"]


def test_answer_rejects_unknown_citation_id() -> None:
    with pytest.raises(ValidationError):
        valid_answer(
            claims=[
                Claim(
                    text="A claim.",
                    cites=["not-in-sources"],
                    support="supported",
                )
            ]
        )


def test_answer_rejects_ineligible_source() -> None:
    unreviewed = approved_passage(
        review_status="candidate_review_pending",
        eligible_for_answer=False,
    )
    with pytest.raises(ValidationError):
        valid_answer(sources=[Hit(passage=unreviewed, score=2.0)])


def test_answer_rejects_supported_claim_without_any_sources() -> None:
    with pytest.raises(ValidationError):
        valid_answer(sources=[])


def test_answered_status_requires_claims() -> None:
    with pytest.raises(ValidationError):
        valid_answer(claims=[])


def test_abstained_answer_can_have_no_claims_or_sources() -> None:
    answer = Answer(
        status="abstained",
        answer_md="I could not find sufficient approved evidence.",
        claims=[],
        sources=[],
        closest_topics=["Randomized Quicksort"],
        corpus_version="test-corpus-v1",
        model="test-provider",
        latency_ms=1,
    )
    assert answer.status == "abstained"


def test_answerability_gate_rejects_ineligible_nested_passage() -> None:
    unreviewed = Passage(
        id="candidate-001",
        lecture=6,
        kind="notes",
        text="Candidate text.",
        section="Unreviewed",
        review_status="candidate_review_pending",
        eligible_for_answer=False,
    )
    hit = Hit(passage=unreviewed, score=9.0).model_dump()

    result = AnswerabilityGate().assess([hit])
    assert result.decision == "abstain"
    assert result.reason == "no_eligible_evidence"


def test_answerability_gate_rejects_missing_nested_eligibility() -> None:
    unreviewed = Passage(
        id="candidate-002",
        lecture=6,
        kind="notes",
        text="Candidate text.",
        section="Unreviewed",
    )
    hit = Hit(passage=unreviewed, score=9.0).model_dump()

    result = AnswerabilityGate().assess([hit])
    assert result.decision == "abstain"
    assert result.reason == "no_eligible_evidence"
