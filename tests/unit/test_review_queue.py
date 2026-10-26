from __future__ import annotations

from algolens.evaluation.review_queue import build_review_queue


def test_review_queue_prioritizes_evidence_mapping_blockers() -> None:
    rows = [
        {
            "question_id": "GQ002",
            "split": "dev",
            "question_type": "compare",
            "label_status": "draft_needs_human_review",
            "gold_passage_ids": ["diag-1"],
            "ids_in_canonical_corpus": [],
            "ids_in_diagnostic_corpus_only": ["diag-1"],
            "ids_unknown_to_both_corpora": [],
            "question_type_review_flags": [],
        },
        {
            "question_id": "GQ001",
            "split": "dev",
            "question_type": "definition_recall",
            "label_status": "draft_needs_human_review",
            "gold_passage_ids": ["missing-1"],
            "ids_in_canonical_corpus": [],
            "ids_in_diagnostic_corpus_only": [],
            "ids_unknown_to_both_corpora": ["missing-1"],
            "question_type_review_flags": ["Advisory type flag"],
        },
        {
            "question_id": "GQ003",
            "split": "test",
            "question_type": "why_reasoning",
            "label_status": "draft_needs_human_review",
            "gold_passage_ids": ["canonical-1"],
            "ids_in_canonical_corpus": ["canonical-1"],
            "ids_in_diagnostic_corpus_only": [],
            "ids_unknown_to_both_corpora": [],
            "question_type_review_flags": [],
        },
    ]

    queue = build_review_queue(rows)

    assert [item["question_id"] for item in queue] == ["GQ001", "GQ002", "GQ003"]
    assert [item["priority"] for item in queue] == ["P0", "P0", "P1"]
    assert "passage_ids_unknown_to_both_corpora" in queue[0]["reasons"]
    assert "diagnostic_only_passage_ids" in queue[1]["reasons"]
    assert "human_review_pending" in queue[2]["reasons"]
    assert rows[0]["label_status"] == "draft_needs_human_review"


def test_review_queue_does_not_flag_empty_evidence_for_unanswerable_question() -> None:
    queue = build_review_queue(
        [
            {
                "question_id": "GQ080",
                "split": "test",
                "question_type": "unanswerable_off_topic",
                "label_status": "human_reviewed",
                "gold_passage_ids": [],
                "ids_in_canonical_corpus": [],
                "ids_in_diagnostic_corpus_only": [],
                "ids_unknown_to_both_corpora": [],
                "question_type_review_flags": [],
            }
        ]
    )

    assert queue == []
