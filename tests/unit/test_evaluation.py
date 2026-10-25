from __future__ import annotations

import json
from pathlib import Path

import pytest

from algolens.evaluation.retrieval_metrics import (
    evaluate_rankings,
    ndcg_at_k,
    recall_at_k,
    reciprocal_rank,
)


def test_recall_at_k_counts_relevant_passages_found() -> None:
    assert recall_at_k({"a", "b"}, ["x", "a", "y"], 3) == 0.5


def test_reciprocal_rank_uses_first_relevant_result() -> None:
    assert reciprocal_rank({"b", "c"}, ["x", "b", "c"]) == 0.5


def test_reciprocal_rank_returns_zero_when_no_gold_is_retrieved() -> None:
    assert reciprocal_rank({"gold"}, ["a", "b", "c"]) == 0.0


def test_ndcg_is_one_for_ideal_ordering() -> None:
    assert ndcg_at_k({"a", "b"}, ["a", "b", "x"], 3) == pytest.approx(1.0)


def test_ndcg_rewards_relevant_passage_at_higher_rank() -> None:
    high = ndcg_at_k({"gold"}, ["gold", "noise"], 2)
    low = ndcg_at_k({"gold"}, ["noise", "gold"], 2)
    assert high > low


@pytest.mark.parametrize("metric_k", [0, -1])
def test_metrics_reject_invalid_k(metric_k: int) -> None:
    with pytest.raises(ValueError):
        recall_at_k({"a"}, ["a"], metric_k)

    with pytest.raises(ValueError):
        ndcg_at_k({"a"}, ["a"], metric_k)


def test_metrics_reject_empty_relevance_labels() -> None:
    with pytest.raises(ValueError, match="relevant"):
        recall_at_k(set(), ["a"], 1)

    with pytest.raises(ValueError, match="relevant"):
        reciprocal_rank(set(), ["a"])

    with pytest.raises(ValueError, match="relevant"):
        ndcg_at_k(set(), ["a"], 1)


def test_evaluator_scores_answerable_only_and_counts_unanswerable() -> None:
    questions = [
        {
            "question_id": "Q1",
            "answerable": True,
            "question_type": "recall",
            "gold_passage_ids": ["gold"],
        },
        {
            "question_id": "Q2",
            "answerable": False,
            "question_type": "unanswerable_off_topic",
            "gold_passage_ids": [],
        },
    ]

    report = evaluate_rankings(
        questions,
        {"Q1": ["noise", "gold"], "Q2": ["noise"]},
    )

    assert report["answerable_question_count"] == 1
    assert report["unanswerable_question_count"] == 1
    assert report["retrieval_metrics"]["recall@5"] == 1.0
    assert report["retrieval_metrics"]["mrr@10"] == 0.5
    assert report["retrieval_metrics"]["ndcg@10"] < 1.0


def test_evaluator_rejects_no_answerable_questions() -> None:
    with pytest.raises(ValueError, match="No answerable"):
        evaluate_rankings(
            [
                {
                    "question_id": "Q1",
                    "answerable": False,
                    "question_type": "unanswerable",
                    "gold_passage_ids": [],
                }
            ],
            {"Q1": []},
        )


def test_draft_gold_set_has_30_questions_and_valid_passage_ids() -> None:
    root = Path(".")
    question_path = root / "eval/gold/questions_v0.jsonl"
    chunk_path = root / "corpus/experiments/chunking/children.jsonl"

    questions = [
        json.loads(line)
        for line in question_path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]
    chunks = [
        json.loads(line)
        for line in chunk_path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]

    assert len(questions) == 30
    assert len({row["question_id"] for row in questions}) == 30
    assert sum(row["answerable"] for row in questions) == 25
    assert sum(not row["answerable"] for row in questions) == 5

    chunk_ids = {row["chunk_id"] for row in chunks}
    for row in questions:
        assert row["label_status"] == "draft_needs_human_review"

        if row["answerable"]:
            assert row["gold_passage_ids"]
        else:
            assert row["gold_passage_ids"] == []

        assert set(row["gold_passage_ids"]).issubset(chunk_ids)
