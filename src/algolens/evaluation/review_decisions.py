from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path
from typing import Any

APPROVED_REVIEW_STATUSES = frozenset({"reviewed", "verified", "approved"})
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
EXPECTED_QUESTION_COUNT = 80


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(f"Required JSONL file does not exist: {path}")
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in {path}, line {line_number}.") from exc
        if not isinstance(value, dict):
            raise ValueError(f"Expected a JSON object in {path}, line {line_number}.")
        rows.append(value)
    return rows


def is_production_eligible(chunk: dict[str, Any]) -> bool:
    status = str(chunk.get("review_status", "")).strip().casefold()
    return (
        status in APPROVED_REVIEW_STATUSES
        and chunk.get("eligible_for_answer") is True
        and chunk.get("retrieval_eligible") is True
    )


def validate_review_decisions(
    candidate: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
    canonical_chunks: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Validate explicit human decisions and return reviewed rows without writing files."""
    errors: list[str] = []
    candidate_by_id = {
        str(row.get("question_id", "")).strip(): row
        for row in candidate
        if str(row.get("question_id", "")).strip()
    }
    decision_ids = [str(row.get("question_id", "")).strip() for row in decisions]
    if len(candidate) != EXPECTED_QUESTION_COUNT:
        errors.append(
            f"Expected {EXPECTED_QUESTION_COUNT} candidate questions; found {len(candidate)}."
        )
    if len(candidate_by_id) != len(candidate):
        errors.append("Candidate question IDs are missing or duplicated.")
    if any(not question_id for question_id in decision_ids):
        errors.append("At least one review decision has no question_id.")
    if len(decision_ids) != len(set(decision_ids)):
        errors.append("Review decisions contain duplicate question IDs.")
    if set(decision_ids) != set(candidate_by_id):
        missing = sorted(set(candidate_by_id) - set(decision_ids))
        unknown = sorted(set(decision_ids) - set(candidate_by_id))
        if missing:
            errors.append(f"Review decisions missing candidate IDs: {missing}")
        if unknown:
            errors.append(f"Review decisions contain unknown IDs: {unknown}")

    canonical_by_id = {
        str(chunk.get("chunk_id", "")): chunk
        for chunk in canonical_chunks
        if isinstance(chunk.get("chunk_id"), str) and chunk.get("chunk_id")
    }
    eligible_ids = {
        chunk_id for chunk_id, chunk in canonical_by_id.items() if is_production_eligible(chunk)
    }
    reviewed_rows: list[dict[str, Any]] = []
    for decision in decisions:
        question_id = str(decision.get("question_id", "")).strip() or "<missing-id>"
        if question_id not in candidate_by_id:
            continue
        if decision.get("decision") != "approve":
            errors.append(f"{question_id}: decision must be 'approve' to build the reviewed set.")
        if decision.get("source_checked") is not True:
            errors.append(f"{question_id}: source_checked must be true.")
        reviewer = decision.get("reviewer")
        if not isinstance(reviewer, str) or not reviewer.strip():
            errors.append(f"{question_id}: reviewer is required.")
        reviewed_at = decision.get("reviewed_at")
        valid_date = False
        if isinstance(reviewed_at, str) and DATE_PATTERN.fullmatch(reviewed_at):
            try:
                date.fromisoformat(reviewed_at)
                valid_date = True
            except ValueError:
                pass
        if not valid_date:
            errors.append(f"{question_id}: reviewed_at must be a valid date in YYYY-MM-DD format.")
        question = decision.get("question")
        if not isinstance(question, str) or not question.strip():
            errors.append(f"{question_id}: reviewed question text is required.")
        question_type = decision.get("question_type")
        if not isinstance(question_type, str) or not question_type.strip():
            errors.append(f"{question_id}: reviewed question_type is required.")
        difficulty = decision.get("difficulty")
        if not isinstance(difficulty, str) or not difficulty.strip():
            errors.append(f"{question_id}: reviewed difficulty is required.")
        answerable = decision.get("answerable")
        if not isinstance(answerable, bool):
            errors.append(f"{question_id}: reviewed answerable value must be boolean.")
        key_points = decision.get("key_points")
        if (
            not isinstance(key_points, list)
            or not key_points
            or any(not isinstance(point, str) or not point.strip() for point in key_points)
        ):
            errors.append(f"{question_id}: reviewed key_points must be a non-empty string list.")
        raw_passage_ids = decision.get("gold_passage_ids")
        if not isinstance(raw_passage_ids, list) or any(
            not isinstance(item, str) or not item.strip() for item in raw_passage_ids
        ):
            errors.append(f"{question_id}: gold_passage_ids must be a list of non-empty strings.")
            passage_ids: list[str] = []
        else:
            passage_ids = raw_passage_ids
        if len(passage_ids) != len(set(passage_ids)):
            errors.append(f"{question_id}: duplicate gold passage IDs.")
        if answerable is True and not passage_ids:
            errors.append(f"{question_id}: answerable question needs gold passage IDs.")
        if answerable is False and passage_ids:
            errors.append(f"{question_id}: unanswerable question must have empty gold passage IDs.")
        for passage_id in passage_ids:
            if passage_id not in canonical_by_id:
                errors.append(f"{question_id}: passage {passage_id} is not canonical.")
            elif passage_id not in eligible_ids:
                errors.append(f"{question_id}: passage {passage_id} is not production-eligible.")

        candidate_row = candidate_by_id[question_id]
        split = candidate_row.get("split")
        if split not in {"dev", "test"}:
            errors.append(f"{question_id}: candidate split must be dev or test.")
        notes = decision.get("notes", "")
        if not isinstance(notes, str):
            errors.append(f"{question_id}: notes must be a string.")
            notes = ""
        reviewed_rows.append(
            {
                "question_id": question_id,
                "question": question.strip() if isinstance(question, str) else "",
                "question_type": question_type,
                "difficulty": difficulty,
                "answerable": answerable,
                "gold_passage_ids": passage_ids,
                "key_points": key_points,
                "annotation_notes": notes,
                "label_status": "human_verified",
                "split": split,
                "reviewer": reviewer.strip() if isinstance(reviewer, str) else "",
                "reviewed_at": reviewed_at,
            }
        )

    split_counts = {
        split: sum(row.get("split") == split for row in reviewed_rows) for split in ("dev", "test")
    }
    if split_counts != {"dev": 50, "test": 30}:
        errors.append(f"Expected a 50 dev / 30 test split; found {split_counts}.")
    if len(reviewed_rows) != EXPECTED_QUESTION_COUNT:
        errors.append(
            f"Expected {EXPECTED_QUESTION_COUNT} reviewed rows; built {len(reviewed_rows)}."
        )
    return reviewed_rows, errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate explicit human decisions before creating a reviewed gold set."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[3],
        help="AlgoLens repository root.",
    )
    parser.add_argument(
        "--decisions",
        type=Path,
        default=Path("eval/gold/review_decisions_v1.jsonl"),
        help="Decision JSONL path, absolute or relative to the project root.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("eval/gold/questions_v1_reviewed.jsonl"),
        help="Output JSONL path, absolute or relative to the project root.",
    )
    args = parser.parse_args()
    root = args.root.resolve()
    decisions_path = args.decisions if args.decisions.is_absolute() else root / args.decisions
    output_path = args.output if args.output.is_absolute() else root / args.output

    candidate = read_jsonl(root / "eval" / "gold" / "questions_v1_candidate.jsonl")
    decisions = read_jsonl(decisions_path)
    canonical = read_jsonl(root / "corpus" / "processed" / "reviewed_chunks" / "children.jsonl")
    reviewed, errors = validate_review_decisions(candidate, decisions, canonical)
    report = {
        "status": "reviewed_gold_ready" if not errors else "reviewed_gold_blocked",
        "decision_count": len(decisions),
        "reviewed_row_count": len(reviewed),
        "errors": errors,
        "output_written": False,
        "candidate_questions_modified": False,
        "canonical_chunks_modified": False,
        "approval_flags_modified": False,
    }
    if errors:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 2
    if output_path.exists():
        report["status"] = "reviewed_gold_blocked"
        report["errors"] = [f"Output already exists; refusing to overwrite: {output_path}"]
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 2

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in reviewed),
        encoding="utf-8",
    )
    report["output_written"] = True
    report["output_path"] = (
        output_path.relative_to(root).as_posix()
        if output_path.is_relative_to(root)
        else str(output_path)
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
