from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from algolens.answering import AnswerDraft
from algolens.contracts import (
    CitationReference,
    Claim,
    Hit,
    Passage,
)
from algolens.grounded_answering import GroundedAnswerService
from algolens.grounding import (
    ClaimGroundingCheck,
    GroundingReport,
)
from algolens.runtime import build_grounded_answer_service

FIXTURE_ID = "test-approved-quicksort-passage"


class ApprovedFixturePipeline:
    """Return one synthetic, explicitly approved passage for the test."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []
        self.passage = Passage(
            id=FIXTURE_ID,
            lecture=6,
            kind="notes",
            text=(
                "Randomized Quicksort chooses a pivot uniformly at random "
                "from the elements of the current subarray."
            ),
            page=3,
            section="Randomized Quicksort",
            citation=CitationReference(
                kind="notes_page",
                display="Test lecture notes, page 3",
                page_start=3,
                page_end=3,
            ),
            review_status="reviewed",
            eligible_for_answer=True,
        )

    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        self.calls.append((query, top_k))
        return [
            {
                "passage": self.passage.model_dump(mode="python"),
                "score": 0.99,
                "ranks": {"hybrid": 1, "rerank": 1},
            }
        ]


class AlwaysAnswerGate:
    """Test double that isolates runtime composition from threshold tuning."""

    def __init__(self) -> None:
        self.received_hits: list[dict[str, Any]] = []

    def assess(self, hits: list[dict[str, Any]]) -> Any:
        self.received_hits = hits

        class Assessment:
            decision = "answer"
            closest_topics: list[str] = []

        return Assessment()


class FixtureProvider:
    """Generate a deterministic answer citing the approved test passage."""

    def __init__(self) -> None:
        self.calls = 0

    def generate(
        self,
        question: str,
        evidence: Sequence[Hit],
        *,
        allow_partial: bool,
    ) -> AnswerDraft:
        self.calls += 1

        assert evidence
        assert all(
            hit.passage.eligible_for_answer and hit.passage.review_status == "reviewed"
            for hit in evidence
        )

        return AnswerDraft(
            answer_md=(
                "Randomized Quicksort chooses a pivot uniformly at random "
                "from the current subarray."
            ),
            claims=[
                Claim(
                    text=(
                        "Randomized Quicksort chooses a pivot uniformly "
                        "at random from the current subarray."
                    ),
                    cites=[FIXTURE_ID],
                    support="supported",
                )
            ],
        )


class FixtureVerifier:
    """Return a controlled positive grounding report for the test."""

    def __init__(self) -> None:
        self.calls = 0
        self.received_passage_ids: list[str] = []

    def verify(
        self,
        claims: Sequence[Claim],
        passages: Sequence[Passage],
    ) -> GroundingReport:
        self.calls += 1
        self.received_passage_ids = [passage.id for passage in passages]

        checks = tuple(
            ClaimGroundingCheck(
                text=claim.text,
                cites=tuple(claim.cites),
                verdict="supported",
                reason="controlled_positive_test_fixture",
            )
            for claim in claims
        )

        return GroundingReport(
            passed=bool(checks),
            checks=checks,
            thresholds_calibrated=False,
        )


def test_runtime_returns_answer_after_generation_and_verification() -> None:
    pipeline = ApprovedFixturePipeline()
    provider = FixtureProvider()
    verifier = FixtureVerifier()
    gate = AlwaysAnswerGate()

    service = build_grounded_answer_service(
        retrieval_pipeline=pipeline,  # type: ignore[arg-type]
        provider=provider,
        corpus_version="synthetic-integration-test",
        model_id="fake-test-provider",
        top_k=4,
        gate=gate,  # type: ignore[arg-type]
        verifier=verifier,
    )

    question = "How does randomized Quicksort choose its pivot?"
    answer = service.answer(question)

    assert isinstance(service, GroundedAnswerService)
    assert answer.status == "answered"
    assert "uniformly at random" in answer.answer_md

    assert len(answer.sources) == 1
    assert answer.sources[0].passage.id == FIXTURE_ID
    assert answer.sources[0].passage.eligible_for_answer is True

    assert len(answer.claims) == 1
    assert answer.claims[0].cites == [FIXTURE_ID]
    assert answer.claims[0].support == "supported"

    assert pipeline.calls == [(question, 4)]
    assert provider.calls == 1
    assert verifier.calls == 1
    assert verifier.received_passage_ids == [FIXTURE_ID]

    assert len(gate.received_hits) == 1
    assert gate.received_hits[0]["passage"]["eligible_for_answer"] is True

    # This integration test uses a fake verifier, so it must not be mistaken
    # for evidence that real NLI thresholds are calibrated.
    assert verifier.calls == 1
