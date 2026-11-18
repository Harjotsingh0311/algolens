from __future__ import annotations

import pytest

from algolens.evaluation.generation_metrics import (
    evaluate_generation_rows,
    key_point_recall,
    percentile,
)


def test_key_point_recall_measures_expected_token_coverage() -> None:
    score = key_point_recall(
        "A good pivot creates balanced subarrays.",
        ["good pivot", "balanced partition subarrays"],
    )
    assert score == pytest.approx((1.0 + 2 / 3) / 2)


def test_generation_metrics_report_grounding_citations_and_system_values() -> None:
    report = evaluate_generation_rows(
        [
            {
                "answerable": True,
                "status": "answered",
                "answer_md": "A pivot partitions the array.",
                "key_points": ["pivot partitions array"],
                "gold_passage_ids": ["p1", "p2"],
                "citation_ids": ["p1"],
                "claim_support": ["supported"],
                "latency_ms": 100.0,
                "provider_calls": 1,
                "estimated_input_tokens": 20,
                "estimated_output_tokens": 10,
            },
            {
                "answerable": False,
                "status": "abstained",
                "answer_md": "I cannot answer.",
                "key_points": [],
                "gold_passage_ids": [],
                "citation_ids": [],
                "claim_support": [],
                "latency_ms": 20.0,
                "provider_calls": 0,
                "estimated_input_tokens": 5,
                "estimated_output_tokens": 3,
            },
        ]
    )

    assert report["answer_coverage"] == 0.5
    assert report["answerable_coverage"] == 1.0
    assert report["unanswerable_answer_rate"] == 0.0
    assert report["mean_key_point_recall"] == 1.0
    assert report["mean_claim_support"] == 1.0
    assert report["citation_precision"] == 1.0
    assert report["citation_recall"] == 0.5
    assert report["p50_latency_ms"] == 20.0
    assert report["p95_latency_ms"] == 100.0
    assert report["provider_calls_per_question"] == 0.5


def test_percentile_rejects_invalid_fraction() -> None:
    with pytest.raises(ValueError, match="between"):
        percentile([1.0], 1.5)
