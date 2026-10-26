from __future__ import annotations

import json
from pathlib import Path

from algolens.evaluation.gold_audit import audit_gold_candidate


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )


def question(question_id: int, *, split: str = "dev") -> dict[str, object]:
    question_types = (
        ["definition_recall"] * 15
        + ["why_reasoning"] * 20
        + ["procedure_trace"] * 10
        + ["compare"] * 10
        + ["multi_hop"] * 10
        + ["unanswerable"] * 15
    )
    return {
        "question_id": f"GQ{question_id:03d}",
        "question": f"Question {question_id}?",
        "question_type": question_types[question_id - 1],
        "difficulty": "easy",
        "answerable": True,
        "gold_passage_ids": ["diag-1"],
        "key_points": ["A source-backed point."],
        "label_status": "draft_needs_human_review",
        "split": split,
    }


def create_fixture(root: Path) -> None:
    rows = [question(index) for index in range(1, 51)]
    rows.extend(question(index, split="test") for index in range(51, 81))
    write_jsonl(root / "eval/gold/questions_v1_candidate.jsonl", rows)
    write_jsonl(
        root / "corpus/processed/reviewed_chunks/children.jsonl",
        [{"chunk_id": "canonical-1"}],
    )
    write_jsonl(
        root / "corpus/experiments/chunking/children.jsonl",
        [{"chunk_id": "diag-1"}, {"chunk_id": "canonical-1"}],
    )


def test_gold_audit_reports_diagnostic_ids_without_promoting_them(tmp_path: Path) -> None:
    create_fixture(tmp_path)

    report = audit_gold_candidate(tmp_path)

    assert report["status"] == "gold_candidate_audit_completed"
    assert report["question_count"] == 80
    assert report["split_counts"] == {"dev": 50, "test": 30}
    assert report["passage_ids_present_in_diagnostic_only"] == ["diag-1"]
    assert report["draft_needs_human_review_count"] == 80
    assert report["final_evaluation_permitted"] is False
    assert report["candidate_questions_modified"] is False
    assert report["approval_flags_modified"] is False


def test_gold_audit_flags_duplicate_question_ids(tmp_path: Path) -> None:
    create_fixture(tmp_path)
    candidate = tmp_path / "eval/gold/questions_v1_candidate.jsonl"
    rows = [json.loads(line) for line in candidate.read_text(encoding="utf-8").splitlines()]
    rows[1]["question_id"] = rows[0]["question_id"]
    write_jsonl(candidate, rows)

    report = audit_gold_candidate(tmp_path)

    assert report["status"] == "gold_candidate_audit_has_errors"
    assert any("Duplicate question IDs" in error for error in report["structural_errors"])


def test_gold_audit_distinguishes_unknown_ids_from_diagnostic_only(tmp_path: Path) -> None:
    create_fixture(tmp_path)
    candidate = tmp_path / "eval/gold/questions_v1_candidate.jsonl"
    rows = [json.loads(line) for line in candidate.read_text(encoding="utf-8").splitlines()]
    rows[0]["gold_passage_ids"] = ["not-found"]
    write_jsonl(candidate, rows)

    report = audit_gold_candidate(tmp_path)

    assert report["passage_ids_unknown_to_both"] == ["not-found"]
    assert report["passage_ids_present_in_diagnostic_only"] == []
