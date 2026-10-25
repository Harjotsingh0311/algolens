from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from algolens.retrieval.bm25 import is_answer_eligible

Decision = Literal["answer", "partial", "abstain"]


@dataclass(frozen=True, slots=True)
class GateAssessment:
    """A deterministic gate decision plus traceable diagnostic features."""

    decision: Decision
    reason: str
    top_score: float | None
    score_margin: float | None
    supporting_hit_count: int
    closest_topics: tuple[str, ...]
    thresholds_calibrated: bool = False


class AnswerabilityGate:
    """Make a provisional decision from ranked retrieval evidence.

    Cross-encoder scores are ranking scores, not probabilities. The default
    thresholds are engineering placeholders and must be calibrated on
    reviewed development labels before the gate is used for production answers.

    Flattened retrieval records must have an approved review_status. Contract-
    shaped Hit records are treated as downstream pipeline output unless they
    explicitly carry an ineligible flag or a review_status that rejects them.
    """

    def __init__(
        self,
        *,
        answer_threshold: float = 1.0,
        partial_threshold: float = 0.0,
        closest_topics_k: int = 3,
    ) -> None:
        for name, value in (
            ("answer_threshold", answer_threshold),
            ("partial_threshold", partial_threshold),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
            ):
                raise ValueError(f"{name} must be a finite number.")

        if answer_threshold <= partial_threshold:
            raise ValueError("answer_threshold must be greater than partial_threshold.")

        if (
            isinstance(closest_topics_k, bool)
            or not isinstance(closest_topics_k, int)
            or closest_topics_k < 1
        ):
            raise ValueError("closest_topics_k must be a positive integer.")

        self.answer_threshold = float(answer_threshold)
        self.partial_threshold = float(partial_threshold)
        self.closest_topics_k = closest_topics_k

    @staticmethod
    def _is_eligible(hit: Mapping[str, Any]) -> bool:
        """Reject explicitly blocked records and unreviewed flattened chunks."""
        if hit.get("eligible_for_answer") is False:
            return False
        if hit.get("retrieval_eligible") is False:
            return False

        passage = hit.get("passage")
        if isinstance(passage, Mapping):
            # Nested contract-shaped records must independently prove eligibility.
            # The shape of a Hit is not proof that its Passage was approved.
            if passage.get("eligible_for_answer") is not True:
                return False
            return is_answer_eligible(passage)

        return is_answer_eligible(hit)

    @staticmethod
    def _score(hit: Mapping[str, Any]) -> float:
        """Read the appropriate reranking score and reject malformed values."""
        if isinstance(hit.get("passage"), Mapping):
            # In the contract, Hit.score is the reranker score.
            field_name = "score"
            raw_score = hit.get(field_name)
        else:
            # Runtime retrieval records retain the RRF score under "score";
            # use the cross-encoder score for the answerability decision.
            field_name = "rerank_score"
            if field_name not in hit:
                raise ValueError("Eligible flattened hits require a rerank_score.")
            raw_score = hit[field_name]

        if (
            isinstance(raw_score, bool)
            or not isinstance(raw_score, (int, float))
            or not math.isfinite(float(raw_score))
        ):
            raise ValueError(f"{field_name} must be a finite number.")

        return float(raw_score)

    @staticmethod
    def _format_seconds(value: Any) -> str | None:
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
            or value < 0
        ):
            return None

        total_seconds = int(value)
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        if hours:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

    @classmethod
    def _topic_label(cls, hit: Mapping[str, Any]) -> str:
        passage = hit.get("passage")
        payload: Mapping[str, Any] = passage if isinstance(passage, Mapping) else hit

        section = payload.get("section") or hit.get("section_start")
        if not section:
            sections = hit.get("sections")
            if isinstance(sections, Sequence) and not isinstance(sections, (str, bytes)):
                section = next(
                    (value for value in sections if isinstance(value, str) and value.strip()),
                    None,
                )

        citation_value: str | None = None
        citation = hit.get("citation")
        if isinstance(citation, Mapping):
            display = citation.get("display")
            if isinstance(display, str) and display.strip():
                citation_value = display.strip()

        if citation_value is None:
            page = payload.get("page")
            if isinstance(page, int) and not isinstance(page, bool) and page > 0:
                citation_value = f"p. {page}"

        if citation_value is None:
            timestamp = cls._format_seconds(
                payload.get("t_start", hit.get("timestamp_start_seconds"))
            )
            if timestamp is not None:
                citation_value = timestamp

        topic = (
            section.strip()
            if isinstance(section, str) and section.strip()
            else "Closest covered passage"
        )
        if citation_value:
            return f"{topic} ({citation_value})"
        return topic

    def assess(
        self,
        hits: Sequence[Mapping[str, Any]],
    ) -> GateAssessment:
        """Assess evidence without mutating the supplied retrieval results."""
        if not hits:
            return GateAssessment(
                decision="abstain",
                reason="no_eligible_evidence",
                top_score=None,
                score_margin=None,
                supporting_hit_count=0,
                closest_topics=(),
            )

        eligible: list[tuple[int, Mapping[str, Any], float]] = []
        for index, hit in enumerate(hits):
            if not isinstance(hit, Mapping):
                raise ValueError("Every hit must be a mapping.")
            if not self._is_eligible(hit):
                continue
            eligible.append((index, hit, self._score(hit)))

        if not eligible:
            return GateAssessment(
                decision="abstain",
                reason="no_eligible_evidence",
                top_score=None,
                score_margin=None,
                supporting_hit_count=0,
                closest_topics=(),
            )

        # Stable sort: equal scores retain the retrieval pipeline's ordering.
        ranked = sorted(eligible, key=lambda item: (-item[2], item[0]))
        top_score = ranked[0][2]
        score_margin = top_score - ranked[1][2] if len(ranked) >= 2 else None
        supporting_hit_count = sum(score >= self.partial_threshold for _, _, score in ranked)

        topic_labels: list[str] = []
        seen_topics: set[str] = set()
        for _, hit, _ in ranked:
            label = self._topic_label(hit)
            if label not in seen_topics:
                seen_topics.add(label)
                topic_labels.append(label)
            if len(topic_labels) >= self.closest_topics_k:
                break

        if top_score >= self.answer_threshold:
            decision: Decision = "answer"
            reason = "strong_retrieval_evidence"
        elif top_score >= self.partial_threshold:
            decision = "partial"
            reason = "partial_evidence"
        else:
            decision = "abstain"
            reason = "below_partial_threshold"

        return GateAssessment(
            decision=decision,
            reason=reason,
            top_score=top_score,
            score_margin=score_margin,
            supporting_hit_count=supporting_hit_count,
            closest_topics=tuple(topic_labels),
            thresholds_calibrated=False,
        )


def decide(hits: Sequence[Mapping[str, Any]]) -> Decision:
    """Public contract operation using provisional default thresholds."""
    return AnswerabilityGate().assess(hits).decision
