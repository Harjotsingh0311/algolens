from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any


def _validate_threshold(name: str, value: float) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
    ):
        raise ValueError(f"{name} threshold must be a finite number.")
    return float(value)


def _validate_inputs(
    answerable: Sequence[bool],
    top_scores: Sequence[float | None],
) -> None:
    if len(answerable) != len(top_scores):
        raise ValueError("answerable and top_scores must have the same length.")
    if not answerable:
        raise ValueError("At least one question is required.")

    for label in answerable:
        if not isinstance(label, bool):
            raise ValueError("Every answerable label must be boolean.")

    for score in top_scores:
        if score is None:
            continue
        if (
            isinstance(score, bool)
            or not isinstance(score, (int, float))
            or not math.isfinite(float(score))
        ):
            raise ValueError("Scores must be finite numbers or None.")


def _risk_coverage_curve(
    answerable: Sequence[bool],
    top_scores: Sequence[float | None],
) -> tuple[list[dict[str, float | int]], float | None]:
    """Sweep unique finite score thresholds, grouping ties together.

    Coverage is accepted questions divided by all questions. Risk is the
    fraction of accepted questions that are unanswerable. Missing scores are
    never accepted and remain in the coverage denominator.
    """
    scored = [(float(score), index) for index, score in enumerate(top_scores) if score is not None]
    if not scored:
        return [], None

    scored.sort(key=lambda item: item[0], reverse=True)

    curve: list[dict[str, float | int]] = []
    accepted_count = 0
    accepted_unanswerable = 0
    position = 0

    while position < len(scored):
        threshold = scored[position][0]

        # Accept every example at this score before recording a curve point.
        while position < len(scored) and scored[position][0] == threshold:
            index = scored[position][1]
            accepted_count += 1
            if not answerable[index]:
                accepted_unanswerable += 1
            position += 1

        coverage = accepted_count / len(answerable)
        risk = accepted_unanswerable / accepted_count

        curve.append(
            {
                "threshold": threshold,
                "accepted_count": accepted_count,
                "coverage": coverage,
                "risk": risk,
            }
        )

    # Area under the risk-coverage curve, with origin (coverage=0, risk=0).
    # Integrate by the trapezoidal rule across the observed score thresholds.
    previous_coverage = 0.0
    previous_risk = 0.0
    area = 0.0

    for point in curve:
        coverage = float(point["coverage"])
        risk = float(point["risk"])
        area += (coverage - previous_coverage) * (risk + previous_risk) / 2.0
        previous_coverage = coverage
        previous_risk = risk

    return curve, area


def evaluate_answerability_scores(
    *,
    answerable: Sequence[bool],
    top_scores: Sequence[float | None],
    answer_threshold: float,
    partial_threshold: float,
) -> dict[str, Any]:
    """Evaluate provisional answer/partial/abstain decisions and risk coverage.

    A numeric score >= answer_threshold maps to "answer".
    A score >= partial_threshold but below answer_threshold maps to "partial".
    Lower scores and missing scores map to "abstain".

    "Partial" counts as accepted for coverage and risk calculations. The
    returned metrics describe the supplied labels; they are not threshold
    calibration and do not establish model quality on unreviewed labels.
    """
    answer_cutoff = _validate_threshold("answer_threshold", answer_threshold)
    partial_cutoff = _validate_threshold("partial_threshold", partial_threshold)

    if answer_cutoff <= partial_cutoff:
        raise ValueError("answer_threshold must be greater than partial_threshold.")

    _validate_inputs(answerable, top_scores)

    predictions: list[str] = []
    for score in top_scores:
        if score is None:
            predictions.append("abstain")
        elif score >= answer_cutoff:
            predictions.append("answer")
        elif score >= partial_cutoff:
            predictions.append("partial")
        else:
            predictions.append("abstain")

    total = len(answerable)
    answer_count = predictions.count("answer")
    partial_count = predictions.count("partial")
    abstain_count = predictions.count("abstain")
    accepted_count = answer_count + partial_count

    correct_count = sum(
        (prediction != "abstain") == label
        for prediction, label in zip(predictions, answerable, strict=True)
    )
    accepted_unanswerable = sum(
        prediction != "abstain" and not label
        for prediction, label in zip(predictions, answerable, strict=True)
    )

    unanswerable_count = sum(not label for label in answerable)
    answerable_count = total - unanswerable_count
    refused_answerable = sum(
        prediction == "abstain" and label
        for prediction, label in zip(predictions, answerable, strict=True)
    )

    risk = accepted_unanswerable / accepted_count if accepted_count else None
    wrong_answer_rate = accepted_unanswerable / unanswerable_count if unanswerable_count else None
    false_refusal_rate = refused_answerable / answerable_count if answerable_count else None

    curve, aurc = _risk_coverage_curve(answerable, top_scores)

    return {
        "schema_version": 1,
        "evaluation": "answerability_and_risk_coverage",
        "thresholds_calibrated": False,
        "answer_threshold": answer_cutoff,
        "partial_threshold": partial_cutoff,
        "question_count": total,
        "answerable_question_count": answerable_count,
        "unanswerable_question_count": unanswerable_count,
        "predictions": predictions,
        "answer_count": answer_count,
        "partial_count": partial_count,
        "abstain_count": abstain_count,
        "accepted_count": accepted_count,
        "coverage": accepted_count / total,
        "risk": risk,
        "accuracy": correct_count / total,
        "wrong_answer_rate_on_unanswerable": wrong_answer_rate,
        "false_refusal_rate_on_answerable": false_refusal_rate,
        "risk_coverage_curve": curve,
        "aurc": aurc,
        "limitations": [
            "Thresholds are supplied configuration, not calibrated probabilities.",
            "Partial decisions count as accepted for coverage and risk.",
            "Questions with missing scores are always abstained on.",
            "Metrics are only as reliable as the answerability labels supplied.",
            "AURC uses the trapezoidal rule over observed unique score thresholds.",
        ],
    }
