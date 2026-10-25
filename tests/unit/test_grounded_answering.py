from __future__ import annotations

from typing import Any

from algolens.contracts import Answer, CitationReference, Claim, Hit, Passage
from algolens.grounded_answering import GroundedAnswerService
from algolens.grounding import GroundingVerifier


def approved_passage() -> Passage:
    return Passage(
        id="p1",
        lecture=6,
        kind="notes",
        text="The pivot is selected uniformly at random.",
        page=1,
        citation=CitationReference(
            kind="notes",
            display="L06 typed notes, page 1",
            page=1,
        ),
        source_id="typed-notes",
        source_url="https://example.invalid/L06_TYPED_NOTES.pdf",
        source_sha256="a" * 64,
        review_status="approved",
        eligible_for_answer=True,
    )


def draft_answer(status: str = "answered") -> Answer:
    claims = (
        [
            Claim(
                text="The pivot is selected uniformly at random.",
                cites=["p1"],
                support="supported",
            )
        ]
        if status == "answered"
        else []
    )
    return Answer(
        status=status,
        answer_md=(
            "The pivot is selected uniformly at random."
            if status == "answered"
            else "I cannot answer from the available evidence."
        ),
        claims=claims,
        sources=[Hit(passage=approved_passage(), score=0.95)],
        closest_topics=[],
        corpus_version="test-v1",
        model="test-model",
        latency_ms=0,
    )


class FakeAnswerService:
    def __init__(self, answer: Answer) -> None:
        self.result = answer
        self.calls = 0

    def answer(self, question: str) -> Answer:
        self.calls += 1
        return self.result


class BrokenVerifier:
    def verify(self, claims: Any, passages: Any) -> Any:
        raise RuntimeError("simulated verification failure")


def test_fully_grounded_answer_is_returned() -> None:
    base = FakeAnswerService(draft_answer())
    verifier = GroundingVerifier(
        scorer=lambda premise, hypothesis: {
            "entailment": 0.96,
            "contradiction": 0.02,
            "neutral": 0.02,
        }
    )

    result = GroundedAnswerService(base, verifier).answer("How is the pivot selected?")

    assert result.status == "answered"
    assert result.claims[0].support == "supported"


def test_weak_evidence_withholds_generated_answer() -> None:
    base = FakeAnswerService(draft_answer())
    verifier = GroundingVerifier(
        scorer=lambda premise, hypothesis: {
            "entailment": 0.20,
            "contradiction": 0.10,
            "neutral": 0.70,
        }
    )

    result = GroundedAnswerService(base, verifier).answer("How is the pivot selected?")

    assert result.status == "abstained"
    assert "The pivot is selected uniformly at random." not in result.answer_md
    assert len(result.claims) == 1
    assert result.claims[0].support == "weak"


def test_verifier_failure_withholds_generated_answer() -> None:
    base = FakeAnswerService(draft_answer())

    result = GroundedAnswerService(base, BrokenVerifier()).answer("How is the pivot selected?")

    assert result.status == "abstained"
    assert "The pivot is selected uniformly at random." not in result.answer_md


def test_existing_abstention_skips_grounding_verifier() -> None:
    base = FakeAnswerService(draft_answer(status="abstained"))

    result = GroundedAnswerService(base, BrokenVerifier()).answer("What does the source say?")

    assert result.status == "abstained"
    assert base.calls == 1
