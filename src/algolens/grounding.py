from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

from algolens.contracts import Claim, Passage
from algolens.nli_scorer import DEFAULT_NLI_MODEL_ID, NLIEntailmentScorer

GroundingVerdict = Literal["supported", "weak", "unsupported"]
APPROVED_REVIEW_STATUSES = frozenset({"reviewed", "verified", "approved"})

# Provisional engineering defaults. These are not calibrated thresholds.
DEFAULT_ENTAILMENT_THRESHOLD = 0.80
DEFAULT_CONTRADICTION_THRESHOLD = 0.80


EntailmentScorer = Callable[[str, str], Mapping[str, float]]


@dataclass(frozen=True)
class ClaimGroundingCheck:
    """Independent evidence assessment for one generated claim."""

    text: str
    cites: tuple[str, ...]
    verdict: GroundingVerdict
    citation_scores: dict[str, dict[str, float]] = field(default_factory=dict)
    reason: str = ""


@dataclass(frozen=True)
class GroundingReport:
    """Overall result for a group of claims."""

    passed: bool
    checks: tuple[ClaimGroundingCheck, ...]
    thresholds_calibrated: bool = False


class GroundingVerifier:
    """Verify claims against explicitly approved evidence using an injected scorer.

    The scorer receives a passage as its premise and a claim as its hypothesis.
    It must return entailment, contradiction, and neutral scores in [0, 1].

    This layer does not prove factual correctness. Its score thresholds must be
    evaluated and calibrated against human-reviewed examples before production use.
    """

    def __init__(
        self,
        scorer: EntailmentScorer,
        *,
        entailment_threshold: float = DEFAULT_ENTAILMENT_THRESHOLD,
        contradiction_threshold: float = DEFAULT_CONTRADICTION_THRESHOLD,
    ) -> None:
        if not callable(scorer):
            raise ValueError("scorer must be callable")

        for name, threshold in (
            ("entailment_threshold", entailment_threshold),
            ("contradiction_threshold", contradiction_threshold),
        ):
            if (
                isinstance(threshold, bool)
                or not isinstance(threshold, (int, float))
                or not math.isfinite(threshold)
                or not 0.0 <= threshold <= 1.0
            ):
                raise ValueError(f"{name} must be a finite number from 0 to 1")

        self.scorer = scorer
        self.entailment_threshold = float(entailment_threshold)
        self.contradiction_threshold = float(contradiction_threshold)
        self.thresholds_calibrated = False

    @classmethod
    def from_nli_model(
        cls,
        *,
        model_id: str = DEFAULT_NLI_MODEL_ID,
        model: Any | None = None,
        entailment_threshold: float = DEFAULT_ENTAILMENT_THRESHOLD,
        contradiction_threshold: float = DEFAULT_CONTRADICTION_THRESHOLD,
    ) -> GroundingVerifier:
        """Construct a verifier backed by the NLI model adapter.

        Model loading remains lazy. Supplying ``model`` is useful for tests;
        omitting it loads the configured CrossEncoder on the first verification
        call. Thresholds remain provisional until calibrated on reviewed claims.
        """
        scorer = NLIEntailmentScorer(model_id=model_id, model=model)
        return cls(
            scorer=scorer,
            entailment_threshold=entailment_threshold,
            contradiction_threshold=contradiction_threshold,
        )

    @staticmethod
    def _normalize_scores(
        scores: object,
    ) -> dict[str, float] | None:
        if not isinstance(scores, Mapping):
            return None

        normalized: dict[str, float] = {}
        for name in ("entailment", "contradiction", "neutral"):
            value = scores.get(name)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or not 0.0 <= value <= 1.0
            ):
                return None
            normalized[name] = float(value)

        return normalized

    @staticmethod
    def _is_approved(passage: Passage) -> bool:
        return (
            passage.eligible_for_answer is True
            and passage.review_status in APPROVED_REVIEW_STATUSES
            and bool(passage.text.strip())
        )

    @staticmethod
    def _failed_check(
        claim: Claim,
        verdict: GroundingVerdict,
        reason: str,
    ) -> ClaimGroundingCheck:
        return ClaimGroundingCheck(
            text=claim.text,
            cites=tuple(claim.cites or ()),
            verdict=verdict,
            reason=reason,
        )

    def verify(
        self,
        claims: Sequence[Claim],
        passages: Sequence[Passage],
    ) -> GroundingReport:
        """Assess each claim; pass only when every claim is supported.

        Every cited ID must resolve uniquely to an approved passage. When any
        citation is missing, ambiguous, or unapproved, scoring is skipped for
        that claim. The generator's own support label is deliberately ignored.
        """
        if not claims:
            return GroundingReport(passed=False, checks=())

        passages_by_id: dict[str, list[Passage]] = {}
        for passage in passages:
            passages_by_id.setdefault(passage.id, []).append(passage)

        checks: list[ClaimGroundingCheck] = []

        for claim in claims:
            claim_text = claim.text.strip()
            citation_ids = list(claim.cites or ())

            if not claim_text:
                checks.append(self._failed_check(claim, "unsupported", "empty_claim"))
                continue

            if not citation_ids:
                checks.append(self._failed_check(claim, "unsupported", "missing_citations"))
                continue

            if any(not isinstance(item, str) or not item.strip() for item in citation_ids):
                checks.append(self._failed_check(claim, "unsupported", "invalid_citation_id"))
                continue

            if len(set(citation_ids)) != len(citation_ids):
                checks.append(self._failed_check(claim, "unsupported", "duplicate_citation_id"))
                continue

            cited_passages: list[tuple[str, Passage]] = []
            invalid_reason: str | None = None

            for citation_id in citation_ids:
                matches = passages_by_id.get(citation_id, [])

                if len(matches) != 1:
                    invalid_reason = "unknown_or_ambiguous_citation"
                    break

                passage = matches[0]
                if not self._is_approved(passage):
                    invalid_reason = "evidence_not_approved"
                    break

                cited_passages.append((citation_id, passage))

            if invalid_reason is not None:
                checks.append(self._failed_check(claim, "unsupported", invalid_reason))
                continue

            citation_scores: dict[str, dict[str, float]] = {}
            scorer_failed = False

            for citation_id, passage in cited_passages:
                try:
                    raw_scores = self.scorer(passage.text, claim_text)
                except Exception:
                    # Fail closed if the scoring backend fails.
                    scorer_failed = True
                    break

                scores = self._normalize_scores(raw_scores)
                if scores is None:
                    scorer_failed = True
                    break

                citation_scores[citation_id] = scores

            if scorer_failed:
                checks.append(
                    ClaimGroundingCheck(
                        text=claim_text,
                        cites=tuple(citation_ids),
                        verdict="unsupported",
                        citation_scores=citation_scores,
                        reason="scorer_error_or_invalid_scores",
                    )
                )
                continue

            # Contradiction takes precedence over a high entailment score.
            if any(
                scores["contradiction"] >= self.contradiction_threshold
                for scores in citation_scores.values()
            ):
                verdict: GroundingVerdict = "unsupported"
                reason = "contradictory_evidence"
            elif all(
                scores["entailment"] >= self.entailment_threshold
                for scores in citation_scores.values()
            ):
                verdict = "supported"
                reason = "all_citations_pass_entailment_threshold"
            else:
                verdict = "weak"
                reason = "insufficient_entailment_score"

            checks.append(
                ClaimGroundingCheck(
                    text=claim_text,
                    cites=tuple(citation_ids),
                    verdict=verdict,
                    citation_scores=citation_scores,
                    reason=reason,
                )
            )

        return GroundingReport(
            passed=bool(checks) and all(check.verdict == "supported" for check in checks),
            checks=tuple(checks),
            thresholds_calibrated=self.thresholds_calibrated,
        )
