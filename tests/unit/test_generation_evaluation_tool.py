from __future__ import annotations

from algolens.contracts import Answer, Claim, Hit, Passage
from tools.run_generation_evaluation import current_system_row, estimated_tokens


class FakeService:
    def answer(self, question: str) -> Answer:
        passage = Passage(
            id="p1",
            lecture=6,
            kind="notes",
            text="A pivot partitions the array.",
            page=3,
            review_status="approved",
            eligible_for_answer=True,
        )
        return Answer(
            status="answered",
            answer_md="A pivot partitions the array.",
            claims=[Claim(text="A pivot partitions the array.", cites=["p1"], support="supported")],
            sources=[Hit(passage=passage, score=3.0)],
            corpus_version="test",
            model="fake",
            latency_ms=10.0,
        )


def test_current_system_row_preserves_metrics_inputs() -> None:
    row = current_system_row(
        FakeService(),
        {
            "question_id": "q1",
            "question": "What does a pivot do?",
            "answerable": True,
            "key_points": ["pivot partitions array"],
            "gold_passage_ids": ["p1"],
        },
    )

    assert row["status"] == "answered"
    assert row["citation_ids"] == ["p1"]
    assert row["claim_support"] == ["supported"]
    assert row["provider_calls"] == 1
    assert row["estimated_input_tokens"] > 0


def test_estimated_tokens_is_positive_for_short_text() -> None:
    assert estimated_tokens("ok") == 1
