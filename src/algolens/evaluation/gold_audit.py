from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

EXPECTED_TYPE_COUNTS = {
    "definition_recall": 15,
    "why_reasoning": 20,
    "procedure_trace": 10,
    "compare": 10,
    "multi_hop": 10,
    "unanswerable": 15,
}
EXPECTED_QUESTION_COUNT = 80


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(f"Required JSONL file does not exist: {path}")
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in {path}, line {line_number}.") from exc
            if not isinstance(row, dict):
                raise ValueError(f"Expected a JSON object in {path}, line {line_number}.")
            rows.append(row)
    return rows


def ids_from(rows: list[dict[str, Any]]) -> set[str]:
    return {
        str(row["chunk_id"])
        for row in rows
        if isinstance(row.get("chunk_id"), str) and row["chunk_id"].strip()
    }


def audit_gold_candidate(root: Path) -> dict[str, Any]:
    candidate_path = root / "eval" / "gold" / "questions_v1_candidate.jsonl"
    canonical_path = root / "corpus" / "processed" / "reviewed_chunks" / "children.jsonl"
    diagnostic_path = root / "corpus" / "experiments" / "chunking" / "children.jsonl"

    questions = read_jsonl(candidate_path)
    canonical_ids = ids_from(read_jsonl(canonical_path))
    diagnostic_ids = ids_from(read_jsonl(diagnostic_path))

    structural_errors: list[str] = []
    question_ids = [str(row.get("question_id", "")).strip() for row in questions]
    duplicate_question_ids = sorted(
        question_id
        for question_id, count in Counter(question_ids).items()
        if question_id and count > 1
    )
    if len(questions) != EXPECTED_QUESTION_COUNT:
        structural_errors.append(
            f"Expected {EXPECTED_QUESTION_COUNT} candidate questions; found {len(questions)}."
        )
    if any(not question_id for question_id in question_ids):
        structural_errors.append("At least one question has no question_id.")
    if duplicate_question_ids:
        structural_errors.append(f"Duplicate question IDs: {duplicate_question_ids}")

    type_counts = Counter(
        (
            "unanswerable"
            if str(row.get("question_type", "")).startswith("unanswerable_")
            else str(row.get("question_type", ""))
        )
        for row in questions
    )
    split_counts = Counter(str(row.get("split", "")) for row in questions)
    if dict(type_counts) != EXPECTED_TYPE_COUNTS:
        structural_errors.append("Question-type distribution differs from the proposal.")

    if split_counts.get("dev", 0) != 50 or split_counts.get("test", 0) != 30:
        structural_errors.append("The candidate split is not exactly 50 dev / 30 test.")
    if sum(split_counts.values()) != len(questions):
        structural_errors.append("One or more questions have an invalid or missing split.")

    for row in questions:
        question_id = str(row.get("question_id", "<missing-id>"))
        if not isinstance(row.get("question"), str) or not row["question"].strip():
            structural_errors.append(f"{question_id}: question text is missing.")
        if not isinstance(row.get("answerable"), bool):
            structural_errors.append(f"{question_id}: answerable must be a Boolean.")
        if not isinstance(row.get("key_points"), list) or not row["key_points"]:
            structural_errors.append(f"{question_id}: key_points must be a non-empty list.")
        if not isinstance(row.get("gold_passage_ids"), list):
            structural_errors.append(f"{question_id}: gold_passage_ids must be a list.")

    referenced_ids: set[str] = set()
    per_question: list[dict[str, Any]] = []
    for row in questions:
        raw_ids = row.get("gold_passage_ids")
        gold_ids = (
            sorted({item for item in raw_ids if isinstance(item, str) and item.strip()})
            if isinstance(raw_ids, list)
            else []
        )
        answerable = row.get("answerable")
        if answerable is True and not gold_ids:
            structural_errors.append(
                f"{row.get('question_id', '<missing-id>')}: answerable question has no gold passage IDs."
            )
        if answerable is False and gold_ids:
            structural_errors.append(
                f"{row.get('question_id', '<missing-id>')}: unanswerable question must not have gold passage IDs."
            )
        if isinstance(raw_ids, list):
            valid_raw_ids = [
                item for item in raw_ids if isinstance(item, str) and item.strip()
            ]
            if len(valid_raw_ids) != len(set(valid_raw_ids)):
                structural_errors.append(
                    f"{row.get('question_id', '<missing-id>')}: duplicate gold passage IDs."
                )
        referenced_ids.update(gold_ids)
        per_question.append(
            {
                "question_id": row.get("question_id"),
                "split": row.get("split"),
                "label_status": row.get("label_status"),
                "gold_passage_ids": gold_ids,
                "ids_in_canonical_corpus": sorted(set(gold_ids) & canonical_ids),
                "ids_in_diagnostic_corpus_only": sorted(
                    (set(gold_ids) & diagnostic_ids) - canonical_ids
                ),
                "ids_unknown_to_both_corpora": sorted(
                    set(gold_ids) - canonical_ids - diagnostic_ids
                ),
            }
        )

    canonical_missing = sorted(referenced_ids - canonical_ids)
    diagnostic_only = sorted((referenced_ids & diagnostic_ids) - canonical_ids)
    unknown_ids = sorted(referenced_ids - canonical_ids - diagnostic_ids)
    review_status_counts = Counter(str(row.get("label_status", "<missing>")) for row in questions)
    draft_count = sum(row.get("label_status") == "draft_needs_human_review" for row in questions)
    reviewed_count = len(questions) - draft_count

    blockers = [
        (
            "Human review is required for every candidate question before labels "
            "can be treated as gold."
        ),
        (
            "Canonical reviewed-corpus mapping is incomplete; diagnostic chunks "
            "are not production evidence."
        ),
        "This report does not approve passages, change labels, or authorize final evaluation.",
    ]
    if unknown_ids:
        blockers.append("Some referenced passage IDs do not exist in either inspected corpus.")

    return {
        "status": (
            "gold_candidate_audit_completed"
            if not structural_errors
            else "gold_candidate_audit_has_errors"
        ),
        "candidate_path": candidate_path.relative_to(root).as_posix(),
        "question_count": len(questions),
        "question_type_counts": dict(sorted(type_counts.items())),
        "expected_question_type_counts": EXPECTED_TYPE_COUNTS,
        "split_counts": dict(sorted(split_counts.items())),
        "label_status_counts": dict(sorted(review_status_counts.items())),
        "draft_needs_human_review_count": draft_count,
        "reviewed_or_other_status_count": reviewed_count,
        "unique_referenced_passage_id_count": len(referenced_ids),
        "canonical_child_id_count": len(canonical_ids),
        "diagnostic_child_id_count": len(diagnostic_ids),
        "passage_ids_missing_from_canonical_count": len(canonical_missing),
        "passage_ids_present_in_diagnostic_only_count": len(diagnostic_only),
        "passage_ids_unknown_to_both_count": len(unknown_ids),
        "passage_ids_missing_from_canonical": canonical_missing,
        "passage_ids_present_in_diagnostic_only": diagnostic_only,
        "passage_ids_unknown_to_both": unknown_ids,
        "per_question": per_question,
        "structural_errors": structural_errors,
        "readiness": "blocked_human_review_and_canonical_mapping",
        "blockers": blockers,
        "final_evaluation_permitted": False,
        "candidate_questions_modified": False,
        "canonical_chunks_modified": False,
        "approval_flags_modified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit the 80-question gold candidate without promoting labels."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[3],
        help="AlgoLens repository root (defaults to the current source checkout).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional report path. Defaults to eval/results/gold_candidate_audit.json.",
    )
    args = parser.parse_args()
    root = args.root.resolve()
    report = audit_gold_candidate(root)
    output_path = args.output or root / "eval" / "results" / "gold_candidate_audit.json"
    if not output_path.is_absolute():
        output_path = root / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if not report["structural_errors"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
