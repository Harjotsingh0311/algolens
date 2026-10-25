from __future__ import annotations

from algolens.contracts import CitationReference, Claim, Passage
from algolens.grounding import GroundingVerifier
from algolens.nli_scorer import DEFAULT_NLI_MODEL_ID, NLIEntailmentScorer


class FakeNLIModel:
    def __init__(self, scores: list[float]) -> None:
        self.scores = scores
        self.calls = 0

    def predict(
        self,
        sentences: list[tuple[str, str]],
        *,
        apply_softmax: bool,
        show_progress_bar: bool,
    ) -> list[list[float]]:
        self.calls += 1
        assert len(sentences) == 1
        assert apply_softmax is True
        assert show_progress_bar is False
        return [self.scores]


def approved_passage() -> Passage:
    return Passage(
        id="p1",
        lecture=6,
        kind="notes",
        text="The pivot is selected uniformly at random.",
        page=1,
        citation=CitationReference(
            kind="notes",
            display="L06 typed notes, page 1",
            page=1,
        ),
        source_id="typed-notes",
        source_url="https://example.invalid/L06_TYPED_NOTES.pdf",
        source_sha256="a" * 64,
        review_status="approved",
        eligible_for_answer=True,
    )


def claim(text: str = "The pivot is selected uniformly at random.") -> Claim:
    return Claim(text=text, cites=["p1"], support="supported")


def test_factory_wires_nli_scorer_into_grounding_verifier() -> None:
    model = FakeNLIModel([0.01, 0.97, 0.02])

    verifier = GroundingVerifier.from_nli_model(
        model_id="test-nli-model",
        model=model,
    )

    assert isinstance(verifier.scorer, NLIEntailmentScorer)
    assert verifier.scorer.model_id == "test-nli-model"
    assert model.calls == 0

    report = verifier.verify([claim()], [approved_passage()])

    assert report.passed is True
    assert report.checks[0].verdict == "supported"
    assert model.calls == 1


def test_nli_factory_defaults_to_documented_model_id() -> None:
    model = FakeNLIModel([0.01, 0.97, 0.02])

    verifier = GroundingVerifier.from_nli_model(model=model)

    assert isinstance(verifier.scorer, NLIEntailmentScorer)
    assert verifier.scorer.model_id == DEFAULT_NLI_MODEL_ID
    assert model.calls == 0


def test_nli_integration_rejects_weak_evidence() -> None:
    model = FakeNLIModel([0.05, 0.10, 0.85])
    verifier = GroundingVerifier.from_nli_model(model=model)

    report = verifier.verify(
        [claim("The algorithm always runs in linear time.")],
        [approved_passage()],
    )

    assert report.passed is False
    assert report.checks[0].verdict == "weak"


def test_nli_integration_rejects_contradictory_evidence() -> None:
    model = FakeNLIModel([0.95, 0.02, 0.03])
    verifier = GroundingVerifier.from_nli_model(model=model)

    report = verifier.verify(
        [claim("The pivot is always the smallest element.")],
        [approved_passage()],
    )

    assert report.passed is False
    assert report.checks[0].verdict == "unsupported"
