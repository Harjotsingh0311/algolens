from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Protocol

DEFAULT_NLI_MODEL_ID = "cross-encoder/nli-deberta-v3-small"

# This ordering is documented by the model card.
_NLI_LABELS = ("contradiction", "entailment", "neutral")


class _CrossEncoder(Protocol):
    """Minimal interface required from a Sentence Transformers CrossEncoder."""

    def predict(
        self,
        sentences: list[tuple[str, str]],
        *,
        apply_softmax: bool,
        show_progress_bar: bool,
    ) -> object: ...


class NLIEntailmentScorer:
    """Return named contradiction, entailment, and neutral probabilities.

    The model is loaded lazily on the first scoring call. Passing a model object
    allows offline unit tests and alternative compatible inference backends.

    Scores are model estimates, not proof that a claim is true.
    """

    def __init__(
        self,
        model_id: str = DEFAULT_NLI_MODEL_ID,
        model: _CrossEncoder | None = None,
    ) -> None:
        if not isinstance(model_id, str) or not model_id.strip():
            raise ValueError("model_id must be a non-empty string")

        self.model_id = model_id.strip()
        self._model = model

    def _get_model(self) -> _CrossEncoder:
        """Load the model only when scoring is first requested."""
        if self._model is None:
            try:
                from sentence_transformers import CrossEncoder
            except ImportError as exc:
                raise RuntimeError(
                    "NLI scoring requires sentence-transformers. "
                    "Install it in the project environment first."
                ) from exc

            self._model = CrossEncoder(self.model_id)

        return self._model

    @staticmethod
    def _normalize_output(output: object) -> dict[str, float]:
        """Validate one three-class probability row and name its values."""
        # NumPy arrays and PyTorch tensors expose tolist(); convert them to
        # ordinary Python lists so tests and model outputs share one code path.
        to_list = getattr(output, "tolist", None)
        if callable(to_list):
            output = to_list()

        if not isinstance(output, Sequence) or isinstance(output, (str, bytes)) or len(output) != 1:
            raise ValueError(
                "NLI model output has an invalid shape; expected one row "
                "containing three class probabilities"
            )

        row = output[0]
        if not isinstance(row, Sequence) or isinstance(row, (str, bytes)) or len(row) != 3:
            raise ValueError(
                "NLI model output has an invalid shape; expected three class probabilities"
            )

        values: list[float] = []
        for value in row:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError("NLI output must contain numeric probabilities")

            probability = float(value)
            if not math.isfinite(probability) or not 0.0 <= probability <= 1.0:
                raise ValueError("NLI output probabilities must be finite and in [0, 1]")
            values.append(probability)

        if not math.isclose(
            sum(values),
            1.0,
            rel_tol=1e-3,
            abs_tol=1e-3,
        ):
            raise ValueError("NLI output probabilities must sum to approximately 1")

        return dict(zip(_NLI_LABELS, values, strict=True))

    def __call__(self, premise: str, hypothesis: str) -> dict[str, float]:
        """Score whether a claim follows from a source passage.

        Args:
            premise: The source passage to use as evidence.
            hypothesis: The atomic claim being checked.

        Returns:
            A dictionary with contradiction, entailment, and neutral scores.

        Raises:
            ValueError: If either input is empty or model output is malformed.
            RuntimeError: If the optional model dependency is unavailable.
        """
        if not isinstance(premise, str) or not premise.strip():
            raise ValueError("premise must be a non-empty string")
        if not isinstance(hypothesis, str) or not hypothesis.strip():
            raise ValueError("hypothesis must be a non-empty string")

        model = self._get_model()
        output = model.predict(
            [(premise.strip(), hypothesis.strip())],
            apply_softmax=True,
            show_progress_bar=False,
        )
        return self._normalize_output(output)
