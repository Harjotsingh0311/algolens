from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]


def test_candidate_gold_v1_is_complete_but_remains_unreviewed() -> None:
    root = Path(".")
    candidate_path = root / "eval/gold/questions_v1_candidate.jsonl"
    experiment_path = root / "corpus/experiments/chunking/children.jsonl"
    canonical_path = root / "corpus/processed/reviewed_chunks/children.jsonl"

    questions = _read_jsonl(candidate_path)
    experiment_chunks = _read_jsonl(experiment_path)
    canonical_chunks = _read_jsonl(canonical_path)

    assert len(questions) == 80
    assert len({row["question_id"] for row in questions}) == 80
    assert {row["question_id"] for row in questions} == {
        f"GQ{number:03d}" for number in range(1, 81)
    }
    assert Counter(row["split"] for row in questions) == {"dev": 50, "test": 30}
    assert all(row["label_status"] == "draft_needs_human_review" for row in questions)
    assert all(type(row["answerable"]) is bool for row in questions)
    assert sum(row["answerable"] is True for row in questions) == 65
    assert sum(row["answerable"] is False for row in questions) == 15

    categories = Counter(
        "unanswerable"
        if str(row["question_type"]).startswith("unanswerable_")
        else str(row["question_type"])
        for row in questions
    )
    assert categories == {
        "definition_recall": 15,
        "why_reasoning": 20,
        "procedure_trace": 10,
        "compare": 10,
        "multi_hop": 10,
        "unanswerable": 15,
    }

    experiment_ids = {str(row["chunk_id"]) for row in experiment_chunks}
    canonical_ids = {str(row["chunk_id"]) for row in canonical_chunks}
    gold_ids = {
        str(passage_id) for row in questions for passage_id in row.get("gold_passage_ids", [])
    }
    assert gold_ids <= experiment_ids
    assert not (gold_ids & canonical_ids), (
        "Candidate labels must not be confused with canonical production evidence."
    )

    for row in questions:
        gold = row.get("gold_passage_ids", [])
        if row["answerable"] is True:
            assert isinstance(gold, list) and gold
        else:
            assert row["answerable"] is False
            assert gold == []


def test_final_preflight_still_uses_v0_draft_set() -> None:
    root = Path(".")
    questions = _read_jsonl(root / "eval/gold/questions_v0.jsonl")
    assert len(questions) == 30
    assert all(row["label_status"] == "draft_needs_human_review" for row in questions)
