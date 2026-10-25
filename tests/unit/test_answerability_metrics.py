from __future__ import annotations

import math

import pytest

from algolens.evaluation.answerability_metrics import (
    evaluate_answerability_scores,
)


def test_score_threshold_metrics_report_decisions_coverage_and_risk() -> None:
    report = evaluate_answerability_scores(
        answerable=[True, False, True, False],
        top_scores=[2.0, 0.4, -0.5, None],
        answer_threshold=1.0,
        partial_threshold=0.0,
    )

    assert report["predictions"] == [
        "answer",
        "partial",
        "abstain",
        "abstain",
    ]
    assert report["answer_count"] == 1
    assert report["partial_count"] == 1
    assert report["abstain_count"] == 2
    assert report["coverage"] == pytest.approx(0.5)
    assert report["risk"] == pytest.approx(0.5)
    assert report["wrong_answer_rate_on_unanswerable"] == pytest.approx(0.5)
    assert report["false_refusal_rate_on_answerable"] == pytest.approx(0.5)
    assert report["accuracy"] == pytest.approx(0.5)
    assert report["thresholds_calibrated"] is False


def test_risk_coverage_curve_is_sorted_by_score() -> None:
    report = evaluate_answerability_scores(
        answerable=[True, False, True, False],
        top_scores=[2.0, 0.4, -0.5, None],
        answer_threshold=1.0,
        partial_threshold=0.0,
    )

    points = report["risk_coverage_curve"]

    assert [p["threshold"] for p in points] == [2.0, 0.4, -0.5]
    assert [p["accepted_count"] for p in points] == [1, 2, 3]
    assert [p["coverage"] for p in points] == pytest.approx([0.25, 0.5, 0.75])
    assert [p["risk"] for p in points] == pytest.approx([0.0, 0.5, 1 / 3])
    assert report["aurc"] == pytest.approx(1 / 6)


def test_equal_scores_are_added_to_curve_as_one_group() -> None:
    report = evaluate_answerability_scores(
        answerable=[True, False, True],
        top_scores=[1.0, 1.0, 0.0],
        answer_threshold=0.5,
        partial_threshold=-0.5,
    )

    points = report["risk_coverage_curve"]

    assert [p["threshold"] for p in points] == [1.0, 0.0]
    assert [p["accepted_count"] for p in points] == [2, 3]
    assert points[0]["risk"] == pytest.approx(0.5)


def test_no_scores_produces_zero_coverage_and_no_aurc() -> None:
    report = evaluate_answerability_scores(
        answerable=[True, False],
        top_scores=[None, None],
        answer_threshold=1.0,
        partial_threshold=0.0,
    )

    assert report["coverage"] == 0.0
    assert report["risk"] is None
    assert report["aurc"] is None
    assert report["risk_coverage_curve"] == []


def test_metrics_handle_single_class_labels() -> None:
    all_answerable = evaluate_answerability_scores(
        answerable=[True, True],
        top_scores=[2.0, -1.0],
        answer_threshold=1.0,
        partial_threshold=0.0,
    )
    all_unanswerable = evaluate_answerability_scores(
        answerable=[False, False],
        top_scores=[2.0, -1.0],
        answer_threshold=1.0,
        partial_threshold=0.0,
    )

    assert all_answerable["wrong_answer_rate_on_unanswerable"] is None
    assert all_unanswerable["false_refusal_rate_on_answerable"] is None


def test_metrics_reject_mismatched_input_lengths() -> None:
    with pytest.raises(ValueError, match="same length"):
        evaluate_answerability_scores(
            answerable=[True, False],
            top_scores=[1.0],
            answer_threshold=1.0,
            partial_threshold=0.0,
        )


def test_metrics_reject_empty_input() -> None:
    with pytest.raises(ValueError, match="At least one"):
        evaluate_answerability_scores(
            answerable=[],
            top_scores=[],
            answer_threshold=1.0,
            partial_threshold=0.0,
        )


@pytest.mark.parametrize(
    "answer_threshold,partial_threshold",
    [(0.0, 0.0), (-1.0, 0.0), (math.inf, 0.0)],
)
def test_metrics_reject_invalid_thresholds(
    answer_threshold: float,
    partial_threshold: float,
) -> None:
    with pytest.raises(ValueError, match="threshold"):
        evaluate_answerability_scores(
            answerable=[True],
            top_scores=[1.0],
            answer_threshold=answer_threshold,
            partial_threshold=partial_threshold,
        )


@pytest.mark.parametrize("invalid_score", [math.nan, math.inf, -math.inf, True])
def test_metrics_reject_invalid_scores(invalid_score: float | bool) -> None:
    with pytest.raises(ValueError, match="finite"):
        evaluate_answerability_scores(
            answerable=[True],
            top_scores=[invalid_score],
            answer_threshold=1.0,
            partial_threshold=0.0,
        )


@pytest.mark.parametrize("invalid_label", [1, 0, "true", None])
def test_metrics_require_boolean_labels(invalid_label: object) -> None:
    with pytest.raises(ValueError, match="boolean"):
        evaluate_answerability_scores(
            answerable=[invalid_label],  # type: ignore[list-item]
            top_scores=[1.0],
            answer_threshold=1.0,
            partial_threshold=0.0,
        )
