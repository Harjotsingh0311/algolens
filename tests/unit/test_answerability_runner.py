from __future__ import annotations

import json
from pathlib import Path

import pytest

from algolens.evaluation.answerability_runner import run_answerability_evaluation


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_answerability_runner_writes_metrics_for_reviewed_labels(tmp_path: Path) -> None:
    gold_path = tmp_path / "gold.jsonl"
    scores_path = tmp_path / "scores.jsonl"
    output_path = tmp_path / "report.json"
    write_jsonl(
        gold_path,
        [
            {"question_id": "Q1", "label_status": "human_verified", "answerable": True},
            {"question_id": "Q2", "label_status": "reviewed", "answerable": False},
        ],
    )
    write_jsonl(
        scores_path,
        [{"question_id": "Q1", "score": 2.0}, {"question_id": "Q2", "score": 0.2}],
    )

    report = run_answerability_evaluation(
        root=tmp_path,
        gold_path=gold_path,
        scores_path=scores_path,
        output_path=output_path,
        answer_threshold=1.0,
        partial_threshold=0.0,
    )

    assert report["status"] == "provisional_answerability_metrics"
    assert report["metrics"]["predictions"] == ["answer", "partial"]
    assert report["metrics"]["risk"] == pytest.approx(0.5)
    assert json.loads(output_path.read_text(encoding="utf-8"))["score_count"] == 2


def test_answerability_runner_blocks_unreviewed_gold(tmp_path: Path) -> None:
    gold_path = tmp_path / "gold.jsonl"
    scores_path = tmp_path / "scores.jsonl"
    write_jsonl(
        gold_path,
        [{"question_id": "Q1", "label_status": "draft_needs_human_review", "answerable": True}],
    )
    write_jsonl(scores_path, [{"question_id": "Q1", "score": 1.0}])

    with pytest.raises(ValueError, match="human-reviewed gold labels"):
        run_answerability_evaluation(
            root=tmp_path,
            gold_path=gold_path,
            scores_path=scores_path,
            output_path=tmp_path / "report.json",
            answer_threshold=1.0,
            partial_threshold=0.0,
        )


def test_answerability_runner_requires_complete_unique_score_ids(tmp_path: Path) -> None:
    gold_path = tmp_path / "gold.jsonl"
    scores_path = tmp_path / "scores.jsonl"
    write_jsonl(
        gold_path,
        [
            {"question_id": "Q1", "label_status": "human_verified", "answerable": True},
            {"question_id": "Q2", "label_status": "human_verified", "answerable": False},
        ],
    )
    write_jsonl(scores_path, [{"question_id": "Q1", "score": 1.0}])

    with pytest.raises(ValueError, match="Missing scores"):
        run_answerability_evaluation(
            root=tmp_path,
            gold_path=gold_path,
            scores_path=scores_path,
            output_path=tmp_path / "report.json",
            answer_threshold=1.0,
            partial_threshold=0.0,
        )
