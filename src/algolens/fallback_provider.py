from __future__ import annotations

from collections.abc import Sequence

from algolens.answering import AnswerDraft, AnswerProvider
from algolens.contracts import Hit


class ProviderChainError(RuntimeError):
    """Raised when every configured provider fails validation or generation."""


class FallbackAnswerProvider:
    """Try configured providers in order and validate each returned draft.

    Provider-specific error messages are deliberately not propagated because
    HTTP client exceptions can contain URLs, headers, or deployment details.
    The caller may safely fall back to approved sources-only mode.
    """

    def __init__(self, providers: Sequence[AnswerProvider]) -> None:
        self.providers = tuple(providers)
        if not self.providers:
            raise ValueError("At least one answer provider must be configured.")

    def generate(
        self,
        question: str,
        evidence: Sequence[Hit],
        *,
        allow_partial: bool,
    ) -> AnswerDraft:
        """Return the first structurally valid draft grounded in supplied IDs."""
        if not isinstance(question, str) or not question.strip():
            raise ValueError("question must be a non-empty string.")
        if not evidence:
            raise ValueError("At least one approved evidence passage is required.")

        evidence_ids = {hit.passage.id for hit in evidence}
        for provider in self.providers:
            try:
                raw_draft = provider.generate(
                    question,
                    evidence,
                    allow_partial=allow_partial,
                )
                draft = AnswerDraft.model_validate(raw_draft)
                cited_ids = {passage_id for claim in draft.claims for passage_id in claim.cites}
                if not cited_ids.issubset(evidence_ids):
                    raise ValueError("Provider draft cites passage IDs absent from evidence.")
                return draft
            except Exception:
                # A provider failure or an invalid response triggers the next
                # configured provider. Do not log raw exceptions or credentials.
                continue

        raise ProviderChainError(
            "All configured answer providers failed; approved sources remain available."
        ) from None
