from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import pytest

from algolens.answering import AnswerDraft
from algolens.contracts import CitationReference, Claim, Hit, Passage
from algolens.fallback_provider import FallbackAnswerProvider, ProviderChainError


def approved_hit(
    *, review_status: str = "reviewed", eligible_for_answer: bool = True
) -> Hit:
    passage = Passage(
        id="passage-001",
        lecture=6,
        kind="notes",
        text="Randomized Quicksort chooses a pivot uniformly at random.",
        page=5,
        citation=CitationReference(
            kind="pdf_page",
            display="p. 5",
            page_start=5,
            page_end=5,
        ),
        source_id="L06_TYPED_NOTES",
        review_status=review_status,
        eligible_for_answer=eligible_for_answer,
    )
    return Hit(passage=passage, score=0.9, ranks={"hybrid": 1})


def valid_draft() -> AnswerDraft:
    return AnswerDraft(
        answer_md="The pivot is chosen at random [p. 5].",
        claims=[
            Claim(
                text="The pivot is chosen at random.",
                cites=["passage-001"],
                support="supported",
            )
        ],
    )


class StubProvider:
    def __init__(
        self,
        *,
        result: AnswerDraft | Mapping[str, Any] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.result = result if result is not None else valid_draft()
        self.error = error
        self.calls = 0

    def generate(
        self,
        question: str,
        evidence: Sequence[Hit],
        *,
        allow_partial: bool,
    ) -> AnswerDraft | Mapping[str, Any]:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.result


def test_fallback_provider_tries_secondary_after_primary_failure() -> None:
    primary = StubProvider(error=RuntimeError("secret key must never appear"))
    fallback = StubProvider()

    result = FallbackAnswerProvider([primary, fallback]).generate(
        "How is the pivot selected?",
        [approved_hit()],
        allow_partial=False,
    )

    assert result.answer_md == valid_draft().answer_md
    assert primary.calls == 1
    assert fallback.calls == 1


def test_invalid_primary_citations_trigger_fallback() -> None:
    bad_primary = StubProvider(
        result=AnswerDraft(
            answer_md="Bad citation.",
            claims=[
                Claim(
                    text="Unknown source.",
                    cites=["not-in-evidence"],
                    support="supported",
                )
            ],
        )
    )
    fallback = StubProvider()

    result = FallbackAnswerProvider([bad_primary, fallback]).generate(
        "How is the pivot selected?",
        [approved_hit()],
        allow_partial=False,
    )

    assert result == valid_draft()
    assert bad_primary.calls == 1
    assert fallback.calls == 1


def test_all_provider_failures_raise_only_a_sanitized_error() -> None:
    chain = FallbackAnswerProvider(
        [
            StubProvider(error=RuntimeError("private token=do-not-show")),
            StubProvider(error=TimeoutError("URL contains private data")),
        ]
    )

    with pytest.raises(ProviderChainError) as exc_info:
        chain.generate("Question?", [approved_hit()], allow_partial=False)

    message = str(exc_info.value)
    assert "All configured answer providers failed" in message
    assert "private token" not in message
    assert "do-not-show" not in message
    assert "private data" not in message


def test_provider_chain_rejects_empty_configuration() -> None:
    with pytest.raises(ValueError, match="At least one"):
        FallbackAnswerProvider([])


def test_provider_chain_rejects_empty_evidence_before_calling_provider() -> None:
    provider = StubProvider()
    chain = FallbackAnswerProvider([provider])

    with pytest.raises(ValueError, match="evidence"):
        chain.generate("Question?", [], allow_partial=False)

    assert provider.calls == 0



def test_provider_chain_rejects_unapproved_evidence_without_calling_provider() -> None:
    provider = StubProvider()
    chain = FallbackAnswerProvider([provider])
    unapproved = approved_hit(
        review_status="candidate_review_pending",
        eligible_for_answer=False,
    )

    with pytest.raises(ValueError, match="explicitly approved"):
        chain.generate("Question?", [unapproved], allow_partial=False)

    assert provider.calls == 0


def test_provider_chain_rejects_duplicate_evidence_ids_without_calling_provider() -> None:
    provider = StubProvider()
    chain = FallbackAnswerProvider([provider])
    evidence = approved_hit()

    with pytest.raises(ValueError, match="duplicate"):
        chain.generate("Question?", [evidence, evidence], allow_partial=False)

    assert provider.calls == 0
