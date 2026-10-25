from __future__ import annotations

from typing import Any, Protocol

from algolens.answerability import AnswerabilityGate
from algolens.answering import AnswerProvider, AnswerService
from algolens.grounded_answering import ClaimVerifier, GroundedAnswerService
from algolens.grounding import GroundingVerifier


class RetrievalBackend(Protocol):
    """Minimum retrieval interface required by the runtime composition."""

    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """Return ranked candidate records with source metadata."""
        ...


def build_grounded_answer_service(
    *,
    retrieval_pipeline: RetrievalBackend,
    provider: AnswerProvider,
    corpus_version: str,
    model_id: str,
    top_k: int = 6,
    gate: AnswerabilityGate | None = None,
    verifier: ClaimVerifier | None = None,
) -> GroundedAnswerService:
    """Compose retrieval, answerability, generation, and claim verification.

    The retrieval pipeline remains responsible for hybrid retrieval,
    reranking, and its existing review-eligibility checks.

    AnswerService applies its own eligibility and answerability checks
    before calling the provider. GroundedAnswerService then independently
    checks generated claims before returning an answer.

    If no verifier is injected, the default NLI verifier is constructed
    lazily; the model is not loaded until claim verification runs.
    """
    backend = AnswerService(
        retrieve=lambda question, limit: retrieval_pipeline.search(
            question,
            top_k=limit,
        ),
        provider=provider,
        corpus_version=corpus_version,
        model_id=model_id,
        top_k=top_k,
        gate=gate,
    )

    claim_verifier = verifier if verifier is not None else GroundingVerifier.from_nli_model()

    return GroundedAnswerService(
        answer_service=backend,
        verifier=claim_verifier,
    )
