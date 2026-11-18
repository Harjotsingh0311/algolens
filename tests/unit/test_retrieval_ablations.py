from __future__ import annotations

from typing import Any

from tools.run_retrieval_ablations import fixed_size_baseline


def approved_chunk(chunk_id: str, text: str, ordinal: int) -> dict[str, Any]:
    return {
        "chunk_id": chunk_id,
        "parent_id": "parent",
        "source_id": "source",
        "ordinal": ordinal,
        "text": text,
        "retrieval_text": text,
        "review_status": "approved",
        "eligible_for_answer": True,
        "retrieval_eligible": True,
    }


def test_fixed_size_baseline_remaps_gold_ids_to_containing_windows() -> None:
    chunks = [
        approved_chunk("c1", "one two three", 1),
        approved_chunk("c2", "four five six", 2),
    ]
    questions = [
        {
            "question_id": "q1",
            "question_type": "recall",
            "answerable": True,
            "gold_passage_ids": ["c2"],
        }
    ]

    baseline, remapped = fixed_size_baseline(chunks, questions, words_per_chunk=4)

    assert [row["word_count"] for row in baseline] == [4, 2]
    assert baseline[0]["origin_chunk_ids"] == ["c1", "c2"]
    assert remapped[0]["gold_passage_ids"] == [
        "naive-fixed-512-0001",
        "naive-fixed-512-0002",
    ]
    assert questions[0]["gold_passage_ids"] == ["c2"]
