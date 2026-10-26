from __future__ import annotations

from typing import Any

from algolens.evaluation.review_decisions import build_review_template, validate_review_decisions


def make_rows() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    candidate: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    for index in range(1, 81):
        question_id = f"GQ{index:03d}"
        split = "dev" if index <= 50 else "test"
        candidate.append({"question_id": question_id, "split": split})
        if index <= 15:
            question_type = "definition_recall"
        elif index <= 35:
            question_type = "why_reasoning"
        elif index <= 45:
            question_type = "procedure_trace"
        elif index <= 55:
            question_type = "compare"
        elif index <= 65:
            question_type = "multi_hop"
        else:
            question_type = "unanswerable_off_topic"
        answerable = index <= 65
        decisions.append(
            {
                "question_id": question_id,
                "decision": "approve",
                "source_checked": True,
                "reviewer": "Reviewer",
                "reviewed_at": "2026-10-26",
                "question": f"Reviewed question {index}?",
                "question_type": question_type,
                "difficulty": "easy",
                "answerable": answerable,
                "key_points": ["A checked key point."],
                "gold_passage_ids": ["canon-1"] if answerable else [],
                "notes": "",
            }
        )
    return candidate, decisions


def canonical_chunks() -> list[dict[str, Any]]:
    return [
        {
            "chunk_id": "canon-1",
            "review_status": "approved",
            "eligible_for_answer": True,
            "retrieval_eligible": True,
        }
    ]


def test_review_decisions_require_explicit_review_and_eligible_canonical_evidence() -> None:
    candidate, decisions = make_rows()

    reviewed, errors = validate_review_decisions(candidate, decisions, canonical_chunks())

    assert errors == []
    assert len(reviewed) == 80
    assert sum(row["split"] == "dev" for row in reviewed) == 50
    assert sum(row["split"] == "test" for row in reviewed) == 30
    assert all(row["label_status"] == "human_verified" for row in reviewed)
    assert all(row["reviewer"] == "Reviewer" for row in reviewed)


def test_review_decisions_reject_diagnostic_only_passage_ids() -> None:
    candidate, decisions = make_rows()
    decisions[0]["gold_passage_ids"] = ["diagnostic-1"]
    canonical = canonical_chunks()

    reviewed, errors = validate_review_decisions(candidate, decisions, canonical)

    assert reviewed
    assert any("GQ001: passage diagnostic-1 is not canonical." in error for error in errors)


def test_review_decisions_reject_unchecked_source_and_unanswerable_evidence() -> None:
    candidate, decisions = make_rows()
    decisions[0]["source_checked"] = False
    decisions[0]["reviewed_at"] = "2026-02-31"
    decisions[1]["answerable"] = False
    decisions[1]["gold_passage_ids"] = ["canon-1"]

    _, errors = validate_review_decisions(candidate, decisions, canonical_chunks())

    assert any("GQ001: source_checked must be true." in error for error in errors)
    assert any("GQ001: reviewed_at must be a valid date" in error for error in errors)
    assert any(
        "GQ002: unanswerable question must have empty gold passage IDs." in error
        for error in errors
    )


def test_review_decisions_reject_duplicate_ids_and_non_approval_decisions() -> None:
    candidate, decisions = make_rows()
    decisions[0]["gold_passage_ids"] = ["canon-1", "canon-1"]
    decisions[1]["decision"] = "revise"

    _, errors = validate_review_decisions(candidate, decisions, canonical_chunks())

    assert any("GQ001: duplicate gold passage IDs." in error for error in errors)
    assert any("GQ002: decision must be 'approve'" in error for error in errors)


def test_review_template_is_unapproved_and_keeps_proposed_ids_separate() -> None:
    template = build_review_template(
        [
            {
                "question_id": "GQ001",
                "question": "What does the pivot do?",
                "question_type": "definition_recall",
                "difficulty": "easy",
                "answerable": True,
                "key_points": ["It partitions the array."],
                "gold_passage_ids": ["diagnostic-1"],
            }
        ]
    )

    assert len(template) == 1
    assert template[0]["decision"] == "pending"
    assert template[0]["source_checked"] is False
    assert template[0]["reviewer"] == ""
    assert template[0]["gold_passage_ids"] == []
    assert template[0]["proposed_gold_passage_ids"] == ["diagnostic-1"]
