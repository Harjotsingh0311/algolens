from __future__ import annotations

from typing import Any


def build_review_queue(per_question: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Prioritize source-review work without changing candidate labels."""
    queue: list[dict[str, Any]] = []
    for item in per_question:
        reasons: list[str] = []
        gold_ids = item.get("gold_passage_ids", [])
        unknown = item.get("ids_unknown_to_both_corpora", [])
        diagnostic = item.get("ids_in_diagnostic_corpus_only", [])
        if unknown:
            reasons.append("passage_ids_unknown_to_both_corpora")
        if diagnostic:
            reasons.append("diagnostic_only_passage_ids")
        if not gold_ids and not str(item.get("question_type", "")).startswith("unanswerable"):
            reasons.append("no_proposed_passage_ids")
        if item.get("question_type_review_flags"):
            reasons.append("question_type_wording_flag")
        if item.get("label_status") != "human_reviewed":
            reasons.append("human_review_pending")
        if not reasons:
            continue
        priority = (
            "P0"
            if any(
                reason in reasons
                for reason in (
                    "passage_ids_unknown_to_both_corpora",
                    "diagnostic_only_passage_ids",
                    "no_proposed_passage_ids",
                )
            )
            else "P1"
        )
        queue.append(
            {
                "question_id": item.get("question_id"),
                "split": item.get("split"),
                "priority": priority,
                "reasons": reasons,
                "gold_passage_ids": gold_ids,
                "canonical_passage_ids": item.get("ids_in_canonical_corpus", []),
                "diagnostic_only_passage_ids": diagnostic,
                "unknown_passage_ids": unknown,
                "question_type_review_flags": item.get("question_type_review_flags", []),
            }
        )
    queue.sort(
        key=lambda item: (
            0 if item["priority"] == "P0" else 1,
            str(item["question_id"]),
        )
    )
    return queue
