from __future__ import annotations

import time
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from algolens.answerability import AnswerabilityGate
from algolens.contracts import (
    APPROVED_REVIEW_STATUSES,
    Answer,
    CitationReference,
    Claim,
    Hit,
    Passage,
)
from algolens.retrieval.bm25 import is_answer_eligible


class EmptyQuestion(ValueError):
    """Raised when the supplied question is blank."""


class AnswerDraft(BaseModel):
    """Untrusted structured output returned by the answer provider."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    answer_md: str = Field(min_length=1)
    claims: list[Claim]


class AnswerProvider(Protocol):
    """Interface implemented by a concrete generation provider."""

    def generate(
        self,
        question: str,
        evidence: Sequence[Hit],
        *,
        allow_partial: bool,
    ) -> AnswerDraft | Mapping[str, Any]:
        """Generate a draft using only the supplied evidence."""
        ...


Retriever = Callable[[str, int], Sequence[Hit | Mapping[str, Any]]]


class AnswerService:
    """Coordinate eligible retrieval, answerability, generation, and validation."""

    def __init__(
        self,
        *,
        retrieve: Retriever,
        provider: AnswerProvider,
        corpus_version: str,
        model_id: str,
        top_k: int = 6,
        gate: AnswerabilityGate | None = None,
    ) -> None:
        if not corpus_version.strip():
            raise ValueError("corpus_version must not be empty.")
        if not model_id.strip():
            raise ValueError("model_id must not be empty.")
        if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k < 1:
            raise ValueError("top_k must be a positive integer.")

        self.retrieve = retrieve
        self.provider = provider
        self.corpus_version = corpus_version
        self.model_id = model_id
        self.top_k = top_k
        self.gate = gate or AnswerabilityGate()

    @staticmethod
    def _as_hit(record: Hit | Mapping[str, Any]) -> Hit | None:
        """Normalize retrieval output without upgrading unreviewed evidence."""
        if isinstance(record, Hit):
            return record

        if not isinstance(record, Mapping):
            return None

        nested_passage = record.get("passage")
        if isinstance(nested_passage, Mapping):
            return Hit.model_validate(record)

        status = str(record.get("review_status", "")).strip().casefold()
        if status not in APPROVED_REVIEW_STATUSES:
            return None
        if record.get("eligible_for_answer") is not True:
            return None
        if not is_answer_eligible(record):
            return None

        chunk_id = record.get("chunk_id")
        if not isinstance(chunk_id, str) or not chunk_id.strip():
            return None

        text = record.get("text") or record.get("retrieval_text")
        if not isinstance(text, str) or not text.strip():
            return None

        source_type = str(record.get("source_type", "")).casefold()
        kind: Literal["spoken", "notes", "handwritten"]
        if any(word in source_type for word in ("transcript", "video", "spoken")):
            kind = "spoken"
        elif "handwritten" in source_type:
            kind = "handwritten"
        else:
            kind = "notes"

        citation = None
        citation_data = record.get("citation")
        if isinstance(citation_data, Mapping):
            citation_kind = citation_data.get("kind")
            citation_display = citation_data.get("display")
            if isinstance(citation_kind, str) and isinstance(citation_display, str):
                citation = CitationReference(
                    kind=citation_kind,
                    display=citation_display,
                    page_start=citation_data.get("page_start", record.get("page_start")),
                    page_end=citation_data.get("page_end", record.get("page_end")),
                    start_seconds=citation_data.get(
                        "start_seconds", record.get("timestamp_start_seconds")
                    ),
                    end_seconds=citation_data.get(
                        "end_seconds", record.get("timestamp_end_seconds")
                    ),
                )

        raw_page = record.get("page", record.get("page_start"))
        page = (
            raw_page
            if isinstance(raw_page, int) and not isinstance(raw_page, bool) and raw_page >= 1
            else None
        )

        section = record.get("section_start", record.get("section", ""))
        if not isinstance(section, str):
            raw_sections = record.get("sections")
            section = (
                next(
                    (item for item in raw_sections if isinstance(item, str) and item.strip()),
                    "",
                )
                if isinstance(raw_sections, Sequence) and not isinstance(raw_sections, (str, bytes))
                else ""
            )

        passage = Passage(
            id=chunk_id,
            lecture=6,
            kind=kind,
            text=text,
            t_start=record.get("t_start", record.get("timestamp_start_seconds")),
            t_end=record.get("t_end", record.get("timestamp_end_seconds")),
            page=page,
            section=section,
            parent_id=record.get("parent_id"),
            pair_id=record.get("pair_id"),
            citation=citation,
            source_id=record.get("source_id"),
            source_url=record.get("source_url"),
            source_sha256=record.get("source_sha256"),
            review_status=status,
            eligible_for_answer=True,
        )

        score = record.get("rerank_score")
        if isinstance(score, bool) or not isinstance(score, (int, float)):
            return None

        ranks: dict[str, int] = {}
        for name in ("bm25_rank", "dense_rank", "hybrid_rank", "rerank_rank"):
            value = record.get(name)
            if isinstance(value, int) and not isinstance(value, bool) and value >= 1:
                ranks[name.removesuffix("_rank")] = value

        return Hit(passage=passage, score=score, ranks=ranks)

    def _abstention(
        self,
        started: float,
        topics: Sequence[str] = (),
    ) -> Answer:
        """Return a generic safe response without exposing internal errors."""
        return Answer(
            status="abstained",
            answer_md=(
                "I could not produce a validated answer from sufficient approved lecture evidence."
            ),
            claims=[],
            sources=[],
            closest_topics=list(topics),
            corpus_version=self.corpus_version,
            model=self.model_id,
            latency_ms=max(0.0, (time.perf_counter() - started) * 1000.0),
        )

    def answer(self, question: str) -> Answer:
        """Answer from approved evidence or return a safe abstention."""
        started = time.perf_counter()

        if not isinstance(question, str) or not question.strip():
            raise EmptyQuestion("Question must not be empty.")

        try:
            records = self.retrieve(question, self.top_k)
            hits: list[Hit] = []

            for record in records:
                hit = self._as_hit(record)
                if hit is not None:
                    hits.append(hit)

            assessment = self.gate.assess([hit.model_dump(mode="python") for hit in hits])
            if assessment.decision == "abstain":
                return self._abstention(started, assessment.closest_topics)

            # Recheck eligibility immediately before calling the provider.
            eligible_hits = [
                hit
                for hit in hits
                if hit.passage.eligible_for_answer
                and hit.passage.review_status.strip().casefold() in APPROVED_REVIEW_STATUSES
                and is_answer_eligible({"review_status": hit.passage.review_status})
            ]
            if not eligible_hits:
                return self._abstention(started, assessment.closest_topics)

            raw_draft = self.provider.generate(
                question,
                eligible_hits,
                allow_partial=assessment.decision == "partial",
            )
            draft = AnswerDraft.model_validate(raw_draft)

            source_ids = {hit.passage.id for hit in eligible_hits}
            cited_ids = {passage_id for claim in draft.claims for passage_id in claim.cites}
            if not cited_ids.issubset(source_ids):
                return self._abstention(started, assessment.closest_topics)

            return Answer(
                status=("partial" if assessment.decision == "partial" else "answered"),
                answer_md=draft.answer_md,
                claims=draft.claims,
                sources=eligible_hits,
                closest_topics=list(assessment.closest_topics),
                corpus_version=self.corpus_version,
                model=self.model_id,
                latency_ms=max(0.0, (time.perf_counter() - started) * 1000.0),
            )

        except (ValidationError, ValueError, TypeError, KeyError):
            return self._abstention(started)
        except Exception:
            # Provider errors and internal details must not leak to the user.
            return self._abstention(started)
