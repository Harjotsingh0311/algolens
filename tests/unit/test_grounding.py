from __future__ import annotations

from algolens.contracts import CitationReference, Claim, Passage
from algolens.grounding import GroundingVerifier


def approved_passage(
    passage_id: str = "p1",
    text: str = "The pivot is selected uniformly at random.",
) -> Passage:
    return Passage(
        id=passage_id,
        lecture=6,
        kind="notes",
        text=text,
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


def make_claim(
    text: str = "The pivot is selected uniformly at random.",
    cites: list[str] | None = None,
    support: str | None = None,
) -> Claim:
    return Claim(
        text=text,
        cites=["p1"] if cites is None else cites,
        support=support,
    )


def test_entailing_evidence_marks_claim_supported() -> None:
    verifier = GroundingVerifier(
        scorer=lambda premise, hypothesis: {
            "entailment": 0.94,
            "contradiction": 0.02,
            "neutral": 0.04,
        }
    )

    report = verifier.verify(
        [make_claim()],
        [approved_passage()],
    )

    assert report.passed is True
    assert report.checks[0].verdict == "supported"


def test_neutral_evidence_marks_claim_weak() -> None:
    verifier = GroundingVerifier(
        scorer=lambda premise, hypothesis: {
            "entailment": 0.22,
            "contradiction": 0.08,
            "neutral": 0.70,
        }
    )

    report = verifier.verify(
        [make_claim(text="The algorithm always runs in linear time.")],
        [approved_passage()],
    )

    assert report.passed is False
    assert report.checks[0].verdict == "weak"


def test_contradicting_evidence_marks_claim_unsupported() -> None:
    verifier = GroundingVerifier(
        scorer=lambda premise, hypothesis: {
            "entailment": 0.03,
            "contradiction": 0.93,
            "neutral": 0.04,
        }
    )

    report = verifier.verify(
        [make_claim(text="The pivot is always the smallest element.")],
        [approved_passage()],
    )

    assert report.passed is False
    assert report.checks[0].verdict == "unsupported"


def test_unknown_citation_fails_without_calling_scorer() -> None:
    scorer_called = False

    def scorer(premise: str, hypothesis: str) -> dict[str, float]:
        nonlocal scorer_called
        scorer_called = True
        return {"entailment": 0.99, "contradiction": 0.0, "neutral": 0.01}

    verifier = GroundingVerifier(scorer=scorer)

    report = verifier.verify(
        [make_claim(cites=["missing-passage"])],
        [approved_passage()],
    )

    assert report.passed is False
    assert report.checks[0].verdict == "unsupported"
    assert scorer_called is False


def test_unapproved_passage_is_never_used_as_evidence() -> None:
    pending = approved_passage().model_copy(
        update={"review_status": "pending_owner_review", "eligible_for_answer": False}
    )
    scorer_called = False

    def scorer(premise: str, hypothesis: str) -> dict[str, float]:
        nonlocal scorer_called
        scorer_called = True
        return {"entailment": 0.99, "contradiction": 0.0, "neutral": 0.01}

    report = GroundingVerifier(scorer=scorer).verify(
        [make_claim()],
        [pending],
    )

    assert report.passed is False
    assert report.checks[0].verdict == "unsupported"
    assert scorer_called is False


def test_claim_without_citations_fails_closed() -> None:
    report = GroundingVerifier(
        scorer=lambda premise, hypothesis: {
            "entailment": 0.99,
            "contradiction": 0.0,
            "neutral": 0.01,
        }
    ).verify(
        [make_claim(cites=[], support=None)],
        [approved_passage()],
    )

    assert report.passed is False
    assert report.checks[0].verdict == "unsupported"


def test_verifier_does_not_trust_generator_support_label() -> None:
    verifier = GroundingVerifier(
        scorer=lambda premise, hypothesis: {
            "entailment": 0.18,
            "contradiction": 0.07,
            "neutral": 0.75,
        }
    )

    # The generated "supported" label must not override the independent scorer.
    report = verifier.verify(
        [make_claim(support="supported")],
        [approved_passage()],
    )

    assert report.passed is False
    assert report.checks[0].verdict == "weak"


def test_empty_claim_list_does_not_count_as_verified() -> None:
    report = GroundingVerifier(
        scorer=lambda premise, hypothesis: {
            "entailment": 0.99,
            "contradiction": 0.0,
            "neutral": 0.01,
        }
    ).verify([], [approved_passage()])

    assert report.passed is False
