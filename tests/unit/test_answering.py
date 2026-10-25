from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pytest

from algolens.answering import AnswerDraft, AnswerService, EmptyQuestion
from algolens.contracts import (
    Answer,
    CitationReference,
    Claim,
    Hit,
    Passage,
)


def eligible_hit(
    *,
    passage_id: str = "passage-001",
    score: float = 2.5,
    text: str = "Randomized Quicksort chooses a pivot at random.",
) -> Hit:
    passage = Passage(
        id=passage_id,
        lecture=6,
        kind="notes",
        text=text,
        section="Randomized Quicksort",
        page=5,
        citation=CitationReference(
            kind="pdf_page",
            display="p. 5",
            page_start=5,
            page_end=5,
        ),
        source_id="L06_TYPED_NOTES",
        source_sha256="a" * 64,
        review_status="reviewed",
        eligible_for_answer=True,
    )
    return Hit(passage=passage, score=score, ranks={"hybrid": 1})


def draft_for(passage_id: str = "passage-001") -> AnswerDraft:
    return AnswerDraft(
        answer_md="Randomized Quicksort chooses a pivot at random [p. 5].",
        claims=[
            Claim(
                text="Randomized Quicksort chooses a pivot at random.",
                cites=[passage_id],
                support="supported",
            )
        ],
    )


class FakeProvider:
    model_id = "fake-provider"

    def __init__(self, result: Any = None, error: Exception | None = None) -> None:
        self.result = result if result is not None else draft_for()
        self.error = error
        self.calls = 0
        self.last_question: str | None = None
        self.last_evidence: Sequence[Hit] = ()
        self.last_allow_partial: bool | None = None

    def generate(
        self,
        question: str,
        evidence: Sequence[Hit],
        *,
        allow_partial: bool,
    ) -> AnswerDraft:
        self.calls += 1
        self.last_question = question
        self.last_evidence = evidence
        self.last_allow_partial = allow_partial
        if self.error is not None:
            raise self.error
        return self.result


def service_for(
    hits: Sequence[Hit],
    provider: FakeProvider,
) -> AnswerService:
    def retrieve(question: str, top_k: int) -> Sequence[Hit]:
        return hits[:top_k]

    return AnswerService(
        retrieve=retrieve,
        provider=provider,
        corpus_version="test-corpus-v1",
        model_id="fake-provider",
    )


def test_answer_service_returns_valid_cited_answer() -> None:
    hit = eligible_hit()
    provider = FakeProvider(draft_for(hit.passage.id))

    answer = service_for([hit], provider).answer("How does randomized Quicksort choose its pivot?")

    assert isinstance(answer, Answer)
    assert answer.status == "answered"
    assert answer.claims[0].cites == [hit.passage.id]
    assert answer.sources[0].passage.id == hit.passage.id
    assert provider.calls == 1


def test_empty_question_raises_domain_error() -> None:
    provider = FakeProvider()
    service = service_for([], provider)

    with pytest.raises(EmptyQuestion):
        service.answer("   ")

    assert provider.calls == 0


def test_no_eligible_evidence_abstains_without_calling_provider() -> None:
    unreviewed = Passage(
        id="candidate-001",
        lecture=6,
        kind="notes",
        text="Unreviewed candidate text.",
        section="Candidate topic",
        review_status="candidate_review_pending",
        eligible_for_answer=False,
    )
    provider = FakeProvider()
    service = service_for([Hit(passage=unreviewed, score=100.0)], provider)

    answer = service.answer("Explain this topic.")

    assert answer.status == "abstained"
    assert answer.claims == []
    assert answer.sources == []
    assert provider.calls == 0


def test_provider_failure_returns_approved_sources_only() -> None:
    hit = eligible_hit()
    provider = FakeProvider(error=RuntimeError("secret provider detail"))
    service = service_for([hit], provider)

    answer = service.answer("Explain randomized Quicksort.")

    assert answer.status == "sources_only"
    assert answer.claims == []
    assert [hit.passage.id for hit in answer.sources] == ["passage-001"]
    assert "secret provider detail" not in answer.answer_md
    assert provider.calls == 1


def test_unknown_citation_id_is_rejected_as_safe_sources_only() -> None:
    hit = eligible_hit()
    provider = FakeProvider(draft_for("missing-passage"))
    service = service_for([hit], provider)

    answer = service.answer("Explain randomized Quicksort.")

    assert answer.status == "sources_only"
    assert answer.claims == []
    assert [hit.passage.id for hit in answer.sources] == ["passage-001"]
    assert "missing-passage" not in answer.answer_md


def test_malformed_provider_output_returns_safe_sources_only() -> None:
    hit = eligible_hit()
    provider = FakeProvider(
        result={
            "answer_md": "An unsupported answer.",
            "claims": [{"text": "Unsupported claim", "cites": [], "support": "supported"}],
        }
    )
    service = service_for([hit], provider)

    answer = service.answer("Explain randomized Quicksort.")

    assert answer.status == "sources_only"
    assert answer.claims == []
    assert [hit.passage.id for hit in answer.sources] == ["passage-001"]


def test_partial_gate_decision_is_passed_to_provider() -> None:
    hit = eligible_hit(score=0.5)
    partial_draft = AnswerDraft(
        answer_md="The available notes partially address the question [p. 5].",
        claims=[
            Claim(
                text="The notes discuss randomized Quicksort.",
                cites=[hit.passage.id],
                support="weak",
            )
        ],
    )
    provider = FakeProvider(result=partial_draft)
    service = service_for([hit], provider)

    answer = service.answer("What do the notes cover?")

    assert answer.status == "partial"
    assert provider.last_allow_partial is True


def test_answer_does_not_include_ineligible_retrieval_results() -> None:
    approved = eligible_hit()
    unreviewed = Passage(
        id="candidate-002",
        lecture=6,
        kind="notes",
        text="Candidate material.",
        section="Unreviewed candidate",
    )
    provider = FakeProvider()
    service = service_for(
        [approved, Hit(passage=unreviewed, score=99.0)],
        provider,
    )

    answer = service.answer("Explain randomized Quicksort.")

    assert answer.status == "answered"
    assert all(hit.passage.eligible_for_answer for hit in answer.sources)
