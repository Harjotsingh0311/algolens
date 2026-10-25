from __future__ import annotations

from typing import Any

from app.app import (
    answer_question,
    build_runtime,
    filter_answer_eligible_chunks,
)


def test_filter_requires_all_explicit_approval_signals() -> None:
    chunks: list[dict[str, Any]] = [
        {
            "chunk_id": "approved",
            "review_status": "approved",
            "eligible_for_answer": True,
            "retrieval_eligible": True,
            "text": "Approved synthetic evidence.",
        },
        {
            "chunk_id": "retrieval-disabled",
            "review_status": "approved_retrieval_disabled",
            "eligible_for_answer": False,
            "retrieval_eligible": False,
            "text": "Not eligible evidence.",
        },
        {
            "chunk_id": "missing-flags",
            "review_status": "approved",
            "text": "Missing explicit approval flags.",
        },
    ]

    result = filter_answer_eligible_chunks(chunks)

    assert [item["chunk_id"] for item in result] == ["approved"]


def test_runtime_fails_closed_for_disabled_corpus(monkeypatch: Any) -> None:
    monkeypatch.setattr(
        "app.app.load_child_chunks",
        lambda: [
            {
                "chunk_id": "candidate",
                "review_status": "approved_retrieval_disabled",
                "eligible_for_answer": False,
                "retrieval_eligible": False,
                "text": "Synthetic disabled passage.",
            }
        ],
    )

    service, readiness = build_runtime()

    assert service is None
    assert readiness["candidate_passages"] == 1
    assert readiness["eligible_passages"] == 0


def test_empty_question_is_rejected_without_runtime(monkeypatch: Any) -> None:
    def forbidden_runtime() -> tuple[None, dict[str, Any]]:
        raise AssertionError("An empty question must not initialize the runtime.")

    monkeypatch.setattr("app.app.get_runtime", forbidden_runtime)

    result = answer_question("   ")

    assert "Enter a question" in result[0]
    assert result[4]["reason"] == "empty_question"


def test_oversized_question_is_rejected_without_runtime(monkeypatch: Any) -> None:
    def forbidden_runtime() -> tuple[None, dict[str, Any]]:
        raise AssertionError("An oversized question must not initialize the runtime.")

    monkeypatch.setattr("app.app.get_runtime", forbidden_runtime)

    result = answer_question("x" * 10_001)

    assert "too long" in result[0]
    assert result[4]["reason"] == "question_too_long"
