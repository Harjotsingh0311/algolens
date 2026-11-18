from __future__ import annotations

import math
import random
from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any


def recall_at_k(
    relevant_ids: set[str],
    ranked_ids: Sequence[str],
    k: int,
) -> float:
    """Fraction of gold passages retrieved within the first k results."""
    if k < 1:
        raise ValueError("k must be at least 1.")
    if not relevant_ids:
        raise ValueError("Recall requires at least one relevant passage.")

    retrieved = set(ranked_ids[:k])
    return len(relevant_ids & retrieved) / len(relevant_ids)


def reciprocal_rank(
    relevant_ids: set[str],
    ranked_ids: Sequence[str],
) -> float:
    """Reciprocal rank of the first retrieved gold passage; zero if absent."""
    if not relevant_ids:
        raise ValueError("Reciprocal rank requires relevant passage IDs.")

    for rank, chunk_id in enumerate(ranked_ids, start=1):
        if chunk_id in relevant_ids:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(
    relevant_ids: set[str],
    ranked_ids: Sequence[str],
    k: int,
) -> float:
    """Binary-relevance normalized discounted cumulative gain."""
    if k < 1:
        raise ValueError("k must be at least 1.")
    if not relevant_ids:
        raise ValueError("nDCG requires at least one relevant passage.")

    dcg = 0.0
    seen: set[str] = set()
    for rank, chunk_id in enumerate(ranked_ids[:k], start=1):
        if chunk_id in relevant_ids and chunk_id not in seen:
            dcg += 1.0 / math.log2(rank + 1)
        seen.add(chunk_id)

    ideal_hits = min(len(relevant_ids), k)
    ideal_dcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))

    return dcg / ideal_dcg if ideal_dcg else 0.0


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _bootstrap_intervals(
    per_question: Sequence[Mapping[str, Any]],
    metric_names: Sequence[str],
    *,
    confidence: float,
    samples: int,
    seed: int,
) -> dict[str, dict[str, float | int]]:
    """Return deterministic percentile confidence intervals over questions."""
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must be between zero and one.")
    if samples < 100:
        raise ValueError("bootstrap_samples must be at least 100.")

    size = len(per_question)
    generator = random.Random(seed)
    distributions: dict[str, list[float]] = {name: [] for name in metric_names}
    for _ in range(samples):
        selected = [per_question[generator.randrange(size)]["metrics"] for _ in range(size)]
        for name in metric_names:
            distributions[name].append(_mean([float(row[name]) for row in selected]))

    tail = (1.0 - confidence) / 2.0
    lower_index = int(tail * (samples - 1))
    upper_index = math.ceil((1.0 - tail) * (samples - 1))
    intervals: dict[str, dict[str, float | int]] = {}
    for name, values in distributions.items():
        values.sort()
        intervals[name] = {
            "confidence": confidence,
            "lower": values[lower_index],
            "upper": values[upper_index],
            "bootstrap_samples": samples,
            "seed": seed,
        }
    return intervals


def evaluate_rankings(
    questions: Sequence[Mapping[str, Any]],
    rankings: Mapping[str, Sequence[str]],
    *,
    k_values: Sequence[int] = (1, 3, 5, 10),
    bootstrap_confidence: float = 0.95,
    bootstrap_samples: int = 2000,
    bootstrap_seed: int = 6046,
) -> dict[str, Any]:
    """Calculate retrieval metrics on answerable questions only.

    Unanswerable questions are counted but excluded from retrieval Recall,
    MRR and nDCG. Abstention requires a separate answerability-gate evaluation.
    """
    if not k_values or any(k < 1 for k in k_values):
        raise ValueError("k_values must contain positive integers.")

    answerable = [q for q in questions if q.get("answerable") is True]
    unanswerable = [q for q in questions if q.get("answerable") is False]

    if not answerable:
        raise ValueError("No answerable questions available for retrieval metrics.")

    per_question: list[dict[str, Any]] = []
    by_type: dict[str, list[dict[str, float]]] = defaultdict(list)

    for question in answerable:
        question_id = str(question["question_id"])
        relevant = set(question["gold_passage_ids"])
        ranked = list(rankings.get(question_id, []))

        if not relevant:
            raise ValueError(f"Answerable question {question_id} has no gold passage IDs.")

        metrics: dict[str, float] = {
            f"recall@{k}": recall_at_k(relevant, ranked, k) for k in k_values
        }
        metrics.update(
            {f"question_recall@{k}": float(bool(relevant & set(ranked[:k]))) for k in k_values}
        )
        metrics["mrr@10"] = reciprocal_rank(relevant, ranked[:10])
        metrics["ndcg@10"] = ndcg_at_k(relevant, ranked, 10)

        row = {
            "question_id": question_id,
            "question_type": str(question["question_type"]),
            "gold_passage_ids": sorted(relevant),
            "retrieved_passage_ids": ranked[:10],
            "metrics": metrics,
        }
        per_question.append(row)
        by_type[str(question["question_type"])].append(metrics)

    metric_names = list(per_question[0]["metrics"])
    averages = {
        name: _mean([row["metrics"][name] for row in per_question]) for name in metric_names
    }
    type_averages = {
        question_type: {name: _mean([row[name] for row in values]) for name in metric_names}
        for question_type, values in sorted(by_type.items())
    }
    confidence_intervals = _bootstrap_intervals(
        per_question,
        metric_names,
        confidence=bootstrap_confidence,
        samples=bootstrap_samples,
        seed=bootstrap_seed,
    )

    return {
        "answerable_question_count": len(answerable),
        "unanswerable_question_count": len(unanswerable),
        "retrieval_metrics": averages,
        "bootstrap_confidence_intervals": confidence_intervals,
        "retrieval_metrics_by_type": type_averages,
        "per_question": per_question,
        "unanswerable_evaluation_note": (
            "Unanswerable questions are excluded from retrieval relevance "
            "metrics. recall@k is the mean fraction of all labelled passages found; "
            "question_recall@k is the fraction of questions with at least one labelled "
            "passage found. This report does not measure abstention or answer quality."
        ),
    }
