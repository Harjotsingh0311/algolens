from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from typing import Any

_TOKEN = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> set[str]:
    return set(_TOKEN.findall(text.casefold()))


def percentile(values: Sequence[float], fraction: float) -> float | None:
    """Return a nearest-rank percentile for a non-empty numeric sequence."""
    if not values:
        return None
    if not 0.0 <= fraction <= 1.0:
        raise ValueError("fraction must be between zero and one.")
    ordered = sorted(float(value) for value in values)
    rank = max(1, math.ceil(fraction * len(ordered)))
    return ordered[rank - 1]


def key_point_recall(answer: str, key_points: Sequence[str]) -> float | None:
    """Measure deterministic lexical coverage of source-reviewed answer key points."""
    if not key_points:
        return None
    answer_tokens = _tokens(answer)
    scores: list[float] = []
    for key_point in key_points:
        expected = _tokens(key_point)
        scores.append(len(answer_tokens & expected) / len(expected) if expected else 0.0)
    return sum(scores) / len(scores)


def evaluate_generation_rows(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Aggregate answer, citation, grounding, latency, and provider-call metrics."""
    if not rows:
        raise ValueError("At least one generation row is required.")

    answerable_rows = [row for row in rows if row.get("answerable") is True]
    unanswerable_rows = [row for row in rows if row.get("answerable") is False]
    accepted_rows = [row for row in rows if row.get("status") in {"answered", "partial"}]
    latencies = [float(row["latency_ms"]) for row in rows if row.get("latency_ms") is not None]

    key_point_scores: list[float] = []
    citation_precisions: list[float] = []
    citation_recalls: list[float] = []
    claim_support_scores: list[float] = []
    total_provider_calls = 0
    estimated_input_tokens = 0
    estimated_output_tokens = 0

    for row in rows:
        answer = str(row.get("answer_md", ""))
        key_points = [str(value) for value in row.get("key_points", [])]
        score = key_point_recall(answer, key_points)
        if row.get("answerable") is True and score is not None:
            key_point_scores.append(score)

        gold = {str(value) for value in row.get("gold_passage_ids", [])}
        citations = {str(value) for value in row.get("citation_ids", [])}
        if citations:
            citation_precisions.append(len(citations & gold) / len(citations))
        if gold:
            citation_recalls.append(len(citations & gold) / len(gold))

        supports = [str(value) for value in row.get("claim_support", [])]
        if supports:
            claim_support_scores.append(
                sum(value == "supported" for value in supports) / len(supports)
            )

        total_provider_calls += int(row.get("provider_calls", 0))
        estimated_input_tokens += int(row.get("estimated_input_tokens", 0))
        estimated_output_tokens += int(row.get("estimated_output_tokens", 0))

    total = len(rows)
    return {
        "schema_version": 1,
        "question_count": total,
        "answerable_question_count": len(answerable_rows),
        "accepted_answer_count": len(accepted_rows),
        "answer_coverage": len(accepted_rows) / total,
        "answerable_coverage": (
            sum(row.get("status") in {"answered", "partial"} for row in answerable_rows)
            / len(answerable_rows)
            if answerable_rows
            else None
        ),
        "unanswerable_answer_rate": (
            sum(row.get("status") in {"answered", "partial"} for row in unanswerable_rows)
            / len(unanswerable_rows)
            if unanswerable_rows
            else None
        ),
        "mean_key_point_recall": (
            sum(key_point_scores) / len(key_point_scores) if key_point_scores else None
        ),
        "mean_claim_support": (
            sum(claim_support_scores) / len(claim_support_scores) if claim_support_scores else None
        ),
        "citation_precision": (
            sum(citation_precisions) / len(citation_precisions) if citation_precisions else None
        ),
        "citation_recall": (
            sum(citation_recalls) / len(citation_recalls) if citation_recalls else None
        ),
        "p50_latency_ms": percentile(latencies, 0.50),
        "p95_latency_ms": percentile(latencies, 0.95),
        "provider_calls_per_question": total_provider_calls / total,
        "estimated_input_tokens_per_question": estimated_input_tokens / total,
        "estimated_output_tokens_per_question": estimated_output_tokens / total,
        "limitations": [
            "Key-point recall is deterministic lexical coverage, not an LLM correctness judge.",
            "Token counts use a four-characters-per-token estimate when provider usage is absent.",
            "Claim support uses the independent verifier labels returned by the application.",
        ],
    }
