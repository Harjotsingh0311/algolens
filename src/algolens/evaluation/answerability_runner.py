from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from algolens.cli import read_jsonl, write_json_atomic
from algolens.evaluation.answerability_metrics import evaluate_answerability_scores


def run_answerability_evaluation(
    *,
    root: Path,
    gold_path: Path,
    scores_path: Path,
    output_path: Path,
    answer_threshold: float,
    partial_threshold: float,
) -> dict[str, Any]:
    """Evaluate externally supplied scores only against explicitly reviewed gold labels."""
    gold = read_jsonl(gold_path)
    score_rows = read_jsonl(scores_path)
    if not gold:
        raise ValueError("Reviewed gold set is empty.")
    if not score_rows:
        raise ValueError("Score input is empty.")

    allowed_statuses = {"human_verified", "reviewed", "verified", "reviewed_or_human_verified"}
    unreviewed = [
        str(row.get("question_id", "<missing-id>"))
        for row in gold
        if row.get("label_status") not in allowed_statuses
    ]
    if unreviewed:
        raise ValueError(
            "Answerability evaluation requires human-reviewed gold labels; "
            f"unreviewed IDs include: {unreviewed[:10]}"
        )

    gold_by_id: dict[str, dict[str, Any]] = {}
    for row in gold:
        question_id = row.get("question_id")
        if not isinstance(question_id, str) or not question_id.strip():
            raise ValueError("Every gold row needs a non-empty question_id.")
        if question_id in gold_by_id:
            raise ValueError(f"Duplicate gold question ID: {question_id}")
        if not isinstance(row.get("answerable"), bool):
            raise ValueError(f"{question_id}: answerable must be a reviewed boolean.")
        gold_by_id[question_id] = row

    scores_by_id: dict[str, float | None] = {}
    for row in score_rows:
        question_id = row.get("question_id")
        if not isinstance(question_id, str) or not question_id.strip():
            raise ValueError("Every score row needs a non-empty question_id.")
        if question_id in scores_by_id:
            raise ValueError(f"Duplicate score question ID: {question_id}")
        if question_id not in gold_by_id:
            raise ValueError(f"Score row references unknown gold question ID: {question_id}")
        score = row.get("score")
        if score is not None and (isinstance(score, bool) or not isinstance(score, (int, float)):
            raise ValueError(f"{question_id}: score must be numeric or null.")
        scores_by_id[question_id] = score

    missing_scores = sorted(set(gold_by_id) - set(scores_by_id))
    if missing_scores:
        raise ValueError(f"Missing scores for gold question IDs: {missing_scores[:10]}")

    ordered_ids = list(gold_by_id)
    metrics = evaluate_answerability_scores(
        answerable=[gold_by_id[question_id]["answerable"] for question_id in ordered_ids],
        top_scores=[scores_by_id[question_id] for question_id in ordered_ids],
        answer_threshold=answer_threshold,
        partial_threshold=partial_threshold,
    )
    report = {
        "status": "provisional_answerability_metrics",
        "gold_path": gold_path.relative_to(root).as_posix()
        if gold_path.is_relative_to(root)
        else str(gold_path),
        "score_path": scores_path.relative_to(root).as_posix()
        if scores_path.is_relative_to(root)
        else str(scores_path),
        "gold_question_count": len(gold),
        "score_count": len(score_rows),
        "metrics": metrics,
        "limitations": [
            "Scores are externally supplied; this command does not run the answerability model.",
            "Thresholds are user-supplied and are not calibrated here.",
            "Use a development split for threshold selection and report held-out test "
            "metrics separately.",
            "Metrics depend on the correctness of human-reviewed answerability labels.",
        ],
    }
    write_json_atomic(output_path, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate supplied answerability scores against reviewed gold labels."
    )
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--gold", type=Path, default=Path("eval/gold/questions_v1_reviewed.jsonl"))
    parser.add_argument("--scores", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("eval/results/answerability_metrics.json"),
    )
    parser.add_argument("--answer-threshold", type=float, default=1.0)
    parser.add_argument("--partial-threshold", type=float, default=0.0)
    args = parser.parse_args()
    root = args.root.resolve()

    def resolve(path: Path) -> Path:
        return path if path.is_absolute() else root / path

    report = run_answerability_evaluation(
        root=root,
        gold_path=resolve(args.gold),
        scores_path=resolve(args.scores),
        output_path=resolve(args.output),
        answer_threshold=args.answer_threshold,
        partial_threshold=args.partial_threshold,
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
