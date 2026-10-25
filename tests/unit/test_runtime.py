from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from algolens.answering import AnswerDraft, AnswerService
from algolens.contracts import Claim, Hit, Passage
from algolens.grounded_answering import GroundedAnswerService
from algolens.grounding import GroundingReport, GroundingVerifier
from algolens.nli_scorer import NLIEntailmentScorer
from algolens.runtime import build_grounded_answer_service


class EmptyRetrievalPipeline:
    """Deterministic pipeline that returns no evidence."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        self.calls.append((query, top_k))
        return []


class NeverGenerateProvider:
    """Fail the test if generation runs without eligible evidence."""

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
        raise AssertionError("Generation must not run without eligible evidence.")


class NeverRunVerifier:
    """Fail the test if an abstention is unnecessarily sent for verification."""

    def __init__(self) -> None:
        self.calls = 0

    def verify(
        self,
        claims: Sequence[Claim],
        passages: Sequence[Passage],
    ) -> GroundingReport:
        self.calls += 1
        raise AssertionError("Verification must not run for an abstained answer.")


def test_runtime_composes_pipeline_and_abstains_without_evidence() -> None:
    pipeline = EmptyRetrievalPipeline()
    provider = NeverGenerateProvider()
    verifier = NeverRunVerifier()

    service = build_grounded_answer_service(
        retrieval_pipeline=pipeline,  # type: ignore[arg-type]
        provider=provider,
        corpus_version="runtime-test",
        model_id="fake-provider",
        top_k=3,
        verifier=verifier,
    )

    assert isinstance(service, GroundedAnswerService)
    assert isinstance(service.answer_service, AnswerService)
    assert service.verifier is verifier

    question = "How does randomized Quicksort choose its pivot?"
    answer = service.answer(question)

    assert answer.status == "abstained"
    assert answer.claims == []
    assert answer.sources == []
    assert pipeline.calls == [(question, 3)]
    assert provider.calls == 0
    assert verifier.calls == 0


def test_runtime_defaults_to_lazy_uncalibrated_nli_verifier() -> None:
    service = build_grounded_answer_service(
        retrieval_pipeline=EmptyRetrievalPipeline(),  # type: ignore[arg-type]
        provider=NeverGenerateProvider(),
        corpus_version="runtime-test",
        model_id="fake-provider",
    )

    assert isinstance(service.verifier, GroundingVerifier)
    assert isinstance(service.verifier.scorer, NLIEntailmentScorer)
    assert service.verifier.thresholds_calibrated is False

    # The CrossEncoder is not downloaded or initialized just by constructing
    # the runtime service. Loading occurs only when verification is requested.
    assert service.verifier.scorer._model is None
