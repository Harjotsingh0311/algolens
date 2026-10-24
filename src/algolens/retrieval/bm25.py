from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

TOKEN_PATTERN = re.compile(
    r"[^\W_]+(?:['’][^\W_]+)*",
    flags=re.UNICODE,
)

APPROVED_REVIEW_STATUSES = frozenset(
    {
        "reviewed",
        "verified",
        "approved",
    }
)


def tokenize(text: str) -> list[str]:
    """Normalize text and split it into Unicode-aware lexical tokens."""
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return TOKEN_PATTERN.findall(normalized)


def is_answer_eligible(chunk: Mapping[str, Any]) -> bool:
    """Only explicitly reviewed chunks can be answer evidence."""
    status = str(chunk.get("review_status", "")).strip().casefold()
    return status in APPROVED_REVIEW_STATUSES


class BM25Index:
    """Small, dependency-free BM25 index over hierarchical child chunks."""

    def __init__(
        self,
        chunks: Sequence[Mapping[str, Any]],
        *,
        include_unreviewed: bool = False,
        k1: float = 1.5,
        b: float = 0.75,
    ) -> None:
        if k1 <= 0:
            raise ValueError("k1 must be positive.")
        if not 0 <= b <= 1:
            raise ValueError("b must be between 0 and 1.")

        self.k1 = k1
        self.b = b
        self.chunks: list[dict[str, Any]] = []
        self.tokens: list[list[str]] = []
        self.term_frequencies: list[Counter[str]] = []
        self.document_frequencies: Counter[str] = Counter()
        seen_ids: set[str] = set()

        for original in chunks:
            chunk = dict(original)
            chunk_id = str(chunk.get("chunk_id", "")).strip()

            if not chunk_id:
                raise ValueError("Every chunk must have a nonempty chunk_id.")
            if chunk_id in seen_ids:
                raise ValueError(f"Duplicate chunk ID: {chunk_id}")
            seen_ids.add(chunk_id)

            if not include_unreviewed and not is_answer_eligible(chunk):
                continue

            text = chunk.get("retrieval_text") or chunk.get("text") or ""
            if not isinstance(text, str):
                raise ValueError(f"Chunk {chunk_id} has invalid text.")

            document_tokens = tokenize(text)
            if not document_tokens:
                continue

            frequencies = Counter(document_tokens)
            self.chunks.append(chunk)
            self.tokens.append(document_tokens)
            self.term_frequencies.append(frequencies)
            self.document_frequencies.update(frequencies.keys())

        self.document_count = len(self.chunks)
        self.document_lengths = [len(tokens) for tokens in self.tokens]
        self.average_document_length = (
            sum(self.document_lengths) / self.document_count if self.document_count else 0.0
        )

    def search(self, query: str, *, top_k: int = 5) -> list[dict[str, Any]]:
        """Return BM25-ranked matches with their original citation metadata."""
        if top_k < 1:
            raise ValueError("top_k must be at least 1.")

        query_tokens = set(tokenize(query))
        if not query_tokens or self.document_count == 0:
            return []

        scored: list[tuple[int, float]] = []

        for document_index, frequencies in enumerate(self.term_frequencies):
            document_length = self.document_lengths[document_index]
            score = 0.0

            for term in query_tokens:
                frequency = frequencies.get(term, 0)
                if frequency == 0:
                    continue

                document_frequency = self.document_frequencies[term]
                inverse_document_frequency = math.log(
                    1.0
                    + (self.document_count - document_frequency + 0.5) / (document_frequency + 0.5)
                )

                length_normalizer = self.k1 * (
                    1.0 - self.b + self.b * document_length / self.average_document_length
                )

                term_score = (
                    inverse_document_frequency
                    * frequency
                    * (self.k1 + 1.0)
                    / (frequency + length_normalizer)
                )
                score += term_score

            if score > 0:
                scored.append((document_index, score))

        scored.sort(key=lambda item: (-item[1], item[0]))

        results: list[dict[str, Any]] = []
        for document_index, score in scored[:top_k]:
            result = dict(self.chunks[document_index])
            result["score"] = score
            result["eligible_for_answer"] = is_answer_eligible(result)
            result["retrieval_method"] = "bm25"
            results.append(result)

        return results


def reciprocal_rank_fusion(
    rankings: Sequence[Sequence[str]],
    *,
    k: int = 60,
    limit: int | None = None,
) -> list[dict[str, float | str]]:
    """Fuse ranked chunk IDs from multiple retrievers using RRF."""
    if k < 1:
        raise ValueError("RRF k must be at least 1.")
    if limit is not None and limit < 1:
        raise ValueError("limit must be at least 1 when provided.")

    scores: dict[str, float] = {}
    first_seen: dict[str, int] = {}
    order_counter = 0

    for ranking in rankings:
        seen_in_ranking: set[str] = set()
        rank = 0

        for chunk_id in ranking:
            if chunk_id in seen_in_ranking:
                continue

            seen_in_ranking.add(chunk_id)
            rank += 1
            scores[chunk_id] = scores.get(chunk_id, 0.0) + (1.0 / (k + rank))

            if chunk_id not in first_seen:
                first_seen[chunk_id] = order_counter
                order_counter += 1

    ranked_ids = sorted(
        scores,
        key=lambda chunk_id: (-scores[chunk_id], first_seen[chunk_id]),
    )

    if limit is not None:
        ranked_ids = ranked_ids[:limit]

    return [{"chunk_id": chunk_id, "score": scores[chunk_id]} for chunk_id in ranked_ids]
