from __future__ import annotations

from typing import Any

import pytest

from algolens.nli_scorer import NLIEntailmentScorer


class FakeCrossEncoder:
    def __init__(self, output: object) -> None:
        self.output = output
        self.pairs: list[tuple[str, str]] | None = None
        self.apply_softmax: bool | None = None
        self.show_progress_bar: bool | None = None

    def predict(
        self,
        pairs: list[tuple[str, str]],
        *,
        apply_softmax: bool,
        show_progress_bar: bool,
    ) -> object:
        self.pairs = pairs
        self.apply_softmax = apply_softmax
        self.show_progress_bar = show_progress_bar
        return self.output


def test_scorer_maps_output_to_named_probabilities() -> None:
    model = FakeCrossEncoder([[0.10, 0.80, 0.10]])
    scorer = NLIEntailmentScorer(model=model)

    result = scorer(
        "The pivot is selected uniformly at random.",
        "The pivot is chosen at random.",
    )

    assert result == {
        "contradiction": pytest.approx(0.10),
        "entailment": pytest.approx(0.80),
        "neutral": pytest.approx(0.10),
    }
    assert model.pairs == [
        (
            "The pivot is selected uniformly at random.",
            "The pivot is chosen at random.",
        )
    ]
    assert model.apply_softmax is True
    assert model.show_progress_bar is False


@pytest.mark.parametrize(
    ("premise", "hypothesis"),
    [
        ("", "A claim."),
        ("A passage.", ""),
        ("   ", "A claim."),
        ("A passage.", "   "),
    ],
)
def test_scorer_rejects_empty_text(
    premise: str,
    hypothesis: str,
) -> None:
    scorer = NLIEntailmentScorer(model=FakeCrossEncoder([[0.1, 0.8, 0.1]]))

    with pytest.raises(ValueError, match="non-empty"):
        scorer(premise, hypothesis)


@pytest.mark.parametrize(
    "output",
    [
        [0.10, 0.80, 0.10],
        [[0.10, 0.80]],
        [[0.10, 0.80, 0.10], [0.20, 0.70, 0.10]],
        "invalid output",
    ],
)
def test_scorer_rejects_invalid_output_shape(output: Any) -> None:
    scorer = NLIEntailmentScorer(model=FakeCrossEncoder(output))

    with pytest.raises(ValueError, match="shape"):
        scorer("A passage.", "A claim.")


@pytest.mark.parametrize(
    "output",
    [
        [[float("nan"), 0.80, 0.20]],
        [[-0.10, 0.80, 0.30]],
        [[0.10, 1.10, -0.20]],
        [[0.20, 0.20, 0.20]],
    ],
)
def test_scorer_rejects_invalid_probabilities(output: Any) -> None:
    scorer = NLIEntailmentScorer(model=FakeCrossEncoder(output))

    with pytest.raises(ValueError, match="probabilit|sum"):
        scorer("A passage.", "A claim.")


def test_scorer_rejects_blank_model_id() -> None:
    with pytest.raises(ValueError, match="model_id"):
        NLIEntailmentScorer(model_id="  ")
