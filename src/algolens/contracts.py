from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

APPROVED_REVIEW_STATUSES = frozenset({"reviewed", "verified", "approved"})


class ContractModel(BaseModel):
    """Base for stable, validated AlgoLens interface models."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)


class CitationReference(ContractModel):
    """A source location that can be rendered as a citation."""

    kind: str = Field(min_length=1)
    display: str = Field(min_length=1)
    page_start: int | None = Field(default=None, ge=1)
    page_end: int | None = Field(default=None, ge=1)
    start_seconds: float | None = Field(default=None, ge=0)
    end_seconds: float | None = Field(default=None, ge=0)

    @field_validator("start_seconds", "end_seconds")
    @classmethod
    def validate_finite_timestamp(cls, value: float | None) -> float | None:
        if value is not None and not math.isfinite(value):
            raise ValueError("Citation timestamps must be finite.")
        return value

    @model_validator(mode="after")
    def validate_location(self) -> CitationReference:
        if (self.page_start is None) != (self.page_end is None):
            raise ValueError("Page citations require both page_start and page_end.")

        if (
            self.page_start is not None
            and self.page_end is not None
            and self.page_end < self.page_start
        ):
            raise ValueError("page_end must not precede page_start.")

        if self.kind in {"pdf_page", "notes_page"} and self.page_start is None:
            raise ValueError("PDF and notes-page citations require page metadata.")

        has_start = self.start_seconds is not None
        has_end = self.end_seconds is not None
        if has_start != has_end:
            raise ValueError("Timestamp citations require both endpoints.")

        if self.kind == "video_timestamp" and not has_start:
            raise ValueError("Video citations require start and end timestamps.")

        if (
            self.start_seconds is not None
            and self.end_seconds is not None
            and self.end_seconds <= self.start_seconds
        ):
            raise ValueError("Citation end time must be greater than start time.")

        return self


class Passage(ContractModel):
    """A source passage with provenance and explicit answer eligibility."""

    id: str = Field(min_length=1)
    lecture: int = Field(ge=1)
    kind: Literal["spoken", "notes", "handwritten"]
    text: str = Field(min_length=1)
    t_start: float | None = Field(default=None, ge=0)
    t_end: float | None = Field(default=None, ge=0)
    page: int | None = Field(default=None, ge=1)
    section: str = ""
    parent_id: str | None = None
    pair_id: str | None = None
    citation: CitationReference | None = None
    source_id: str | None = None
    source_url: str | None = None
    source_sha256: str | None = None
    review_status: str = "unreviewed_extraction"
    eligible_for_answer: bool = False

    @field_validator("t_start", "t_end")
    @classmethod
    def validate_finite_passage_timestamp(cls, value: float | None) -> float | None:
        if value is not None and not math.isfinite(value):
            raise ValueError("Passage timestamps must be finite.")
        return value

    @field_validator("source_sha256")
    @classmethod
    def validate_source_hash(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if len(value) != 64 or any(char not in "0123456789abcdefABCDEF" for char in value):
            raise ValueError("source_sha256 must be a 64-character hexadecimal SHA-256.")
        return value

    @model_validator(mode="after")
    def validate_provenance_and_eligibility(self) -> Passage:
        has_start = self.t_start is not None
        has_end = self.t_end is not None

        if has_start != has_end:
            raise ValueError("Passage timestamps require both endpoints.")

        if self.kind == "spoken" and not has_start:
            raise ValueError("Spoken passages require start and end timestamps.")

        if self.t_start is not None and self.t_end is not None and self.t_end <= self.t_start:
            raise ValueError("Passage end time must be greater than start time.")

        if self.eligible_for_answer and (
            self.review_status.strip().casefold() not in APPROVED_REVIEW_STATUSES
        ):
            raise ValueError("Passage eligibility requires an approved review_status.")

        return self


class Hit(ContractModel):
    """A passage together with its ranking score and available retrieval ranks."""

    passage: Passage
    score: float
    ranks: dict[str, int] = Field(default_factory=dict)

    @field_validator("score", mode="before")
    @classmethod
    def validate_score_input(cls, value: object) -> object:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("Hit score must be a finite numeric value.")
        if not math.isfinite(float(value)):
            raise ValueError("Hit score must be a finite numeric value.")
        return value

    @field_validator("ranks")
    @classmethod
    def validate_ranks(cls, value: dict[str, int]) -> dict[str, int]:
        for name, rank in value.items():
            if not name.strip():
                raise ValueError("Retrieval rank names must be nonempty.")
            if isinstance(rank, bool) or rank < 1:
                raise ValueError("Retrieval ranks must be positive integers.")
        return value


class Claim(ContractModel):
    """One answer claim and its source passage IDs."""

    text: str = Field(min_length=1)
    cites: list[str] = Field(default_factory=list)
    support: Literal["supported", "weak", "unsupported"] | None = None

    @field_validator("cites")
    @classmethod
    def validate_citations(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value]
        if any(not item for item in cleaned):
            raise ValueError("Citation IDs must be nonempty.")
        if len(cleaned) != len(set(cleaned)):
            raise ValueError("Duplicate citation IDs are not allowed.")
        return cleaned

    @model_validator(mode="after")
    def validate_support(self) -> Claim:
        if self.support == "supported" and not self.cites:
            raise ValueError("A supported claim must cite at least one passage.")
        return self


class Answer(ContractModel):
    """Public response object for the UI and evaluation harness."""

    status: Literal["answered", "partial", "abstained", "sources_only"]
    answer_md: str = Field(min_length=1)
    claims: list[Claim] = Field(default_factory=list)
    sources: list[Hit] = Field(default_factory=list)
    closest_topics: list[str] = Field(default_factory=list)
    corpus_version: str = Field(min_length=1)
    model: str = Field(min_length=1)
    latency_ms: float = Field(ge=0)

    @field_validator("latency_ms", mode="before")
    @classmethod
    def validate_latency(cls, value: object) -> object:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("latency_ms must be a finite nonnegative number.")
        if not math.isfinite(float(value)) or value < 0:
            raise ValueError("latency_ms must be a finite nonnegative number.")
        return value

    @model_validator(mode="after")
    def validate_claim_source_consistency(self) -> Answer:
        if self.status in {"answered", "partial"} and not self.claims:
            raise ValueError("Answered and partial responses must contain claim-level records.")

        if self.status == "sources_only" and not self.sources:
            raise ValueError("A sources_only response must contain source evidence.")

        for hit in self.sources:
            passage = hit.passage
            if (
                not passage.eligible_for_answer
                or passage.review_status.strip().casefold() not in APPROVED_REVIEW_STATUSES
            ):
                raise ValueError(f"Answer contains ineligible source passage: {passage.id}")

        available_ids = {hit.passage.id for hit in self.sources}
        for claim in self.claims:
            unknown_ids = set(claim.cites) - available_ids
            if unknown_ids:
                raise ValueError(
                    "Claim references passage IDs absent from answer sources: "
                    + ", ".join(sorted(unknown_ids))
                )

        if self.status == "answered" and any(claim.support != "supported" for claim in self.claims):
            raise ValueError("Every claim in an answered response must be marked supported.")

        return self
