from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from algolens.contracts import Answer, Claim, Passage
from algolens.grounding import GroundingReport

_SAFE_ABSTENTION = (
    "I can't provide a reliable answer from the approved evidence passages. "
    "Please review the available source material."
)


class AnswerBackend(Protocol):
    """Interface for the existing answer-generation service."""

    def answer(self, question: str) -> Answer: ...


class ClaimVerifier(Protocol):
    """Interface for an independent grounding verifier."""

    def verify(
        self,
        claims: Sequence[Claim],
        passages: Sequence[Passage],
    ) -> GroundingReport: ...


class GroundedAnswerService:
    """Return generated answers only when all claims pass grounding checks.

    This wrapper does not replace the existing answer service. It adds an
    independent verification boundary. Any verifier error or malformed report
    results in abstention. Threshold calibration remains a separate task.
    """

    def __init__(
        self,
        answer_service: AnswerBackend,
        verifier: ClaimVerifier,
    ) -> None:
        self.answer_service = answer_service
        self.verifier = verifier

    @staticmethod
    def _with_support_labels(
        claims: Sequence[Claim],
        report: GroundingReport | None,
    ) -> list[Claim]:
        """Return copies of claims labelled with verifier results.

        If the report is missing or does not contain exactly one check per
        claim, label all claims unsupported.
        """
        if report is None or len(report.checks) != len(claims):
            return [claim.model_copy(update={"support": "unsupported"}) for claim in claims]

        return [
            claim.model_copy(update={"support": check.verdict})
            for claim, check in zip(claims, report.checks, strict=True)
        ]

    @staticmethod
    def _abstain(
        answer: Answer,
        report: GroundingReport | None = None,
    ) -> Answer:
        """Withhold generated answer text and return a safe abstention."""
        labelled_claims = GroundedAnswerService._with_support_labels(
            answer.claims,
            report,
        )
        return answer.model_copy(
            update={
                "status": "abstained",
                "answer_md": _SAFE_ABSTENTION,
                "claims": labelled_claims,
            }
        )

    def answer(self, question: str) -> Answer:
        """Generate, verify, then return the answer or abstain safely."""
        generated = self.answer_service.answer(question)

        # Preserve existing abstentions and non-answer results. There is no
        # factual answer text to release through this verification boundary.
        if generated.status not in {"answered", "partial"}:
            return generated

        try:
            passages = [hit.passage for hit in generated.sources]
            report = self.verifier.verify(
                generated.claims,
                passages,
            )
        except Exception:
            # Fail closed without exposing internal verifier errors.
            return self._abstain(generated)

        # Do not rely solely on a boolean flag. Validate the shape and every
        # individual verdict before releasing the generated answer.
        if len(report.checks) != len(generated.claims):
            return self._abstain(generated, report)

        every_claim_supported = all(check.verdict == "supported" for check in report.checks)

        if report.passed is not True or not every_claim_supported:
            return self._abstain(generated, report)

        verified_claims = self._with_support_labels(
            generated.claims,
            report,
        )

        return generated.model_copy(update={"claims": verified_claims})
