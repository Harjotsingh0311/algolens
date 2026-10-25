from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from algolens.answering import AnswerDraft, AnswerService
from algolens.contracts import Claim, Hit
from algolens.retrieval.bm25 import is_answer_eligible
from algolens.retrieval.pipeline import RetrievalPipeline


class CorpusHybridSearch:
    """Return real corpus records through a deterministic test double."""

    def __init__(self, chunks: list[dict[str, Any]]) -> None:
        self.chunks = chunks

    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        candidate_k: int | None = None,
    ) -> list[dict[str, Any]]:
        return [dict(chunk) for chunk in self.chunks[:top_k]]


class RerankerMustNotRun:
    """Fail the test if ineligible evidence reaches reranking."""

    def __init__(self) -> None:
        self.calls = 0

    def rerank(
        self,
        query: str,
        candidates: Sequence[Mapping[str, Any]],
        *,
        top_k: int | None = None,
    ) -> list[dict[str, Any]]:
        self.calls += 1
        raise AssertionError("Reranker must not run without eligible evidence.")


class ProviderMustNotRun:
    """Record generation attempts; this test expects zero."""

    def __init__(self) -> None:
        self.calls = 0

    def generate(
        self,
        question: str,
        evidence: Sequence[Hit],
        *,
        allow_partial: bool,
    ) -> AnswerDraft:
        self.calls += 1
        first_id = evidence[0].passage.id
        return AnswerDraft(
            answer_md="A test answer.",
            claims=[
                Claim(
                    text="A test claim.",
                    cites=[first_id],
                    support="supported",
                )
            ],
        )


def test_current_unapproved_corpus_abstains_before_generation() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    chunk_path = repo_root / "corpus/experiments/chunking/children.jsonl"

    assert chunk_path.is_file(), f"Missing experimental corpus: {chunk_path}"

    chunks: list[dict[str, Any]] = []
    with chunk_path.open(encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                chunks.append(json.loads(line))

    assert chunks, "Expected experimental child chunks."
    assert all(not is_answer_eligible(chunk) for chunk in chunks), (
        "The experimental corpus now contains eligible passages. "
        "Review and update this integration test before changing answer behavior."
    )

    hybrid = CorpusHybridSearch(chunks)
    reranker = RerankerMustNotRun()
    provider = ProviderMustNotRun()

    pipeline = RetrievalPipeline(
        hybrid_index=hybrid,
        reranker=reranker,
        candidate_k=20,
        include_unreviewed=False,
    )
    service = AnswerService(
        retrieve=lambda question, top_k: pipeline.search(question, top_k=top_k),
        provider=provider,
        corpus_version="experimental-corpus-test",
        model_id="fake-provider",
    )

    answer = service.answer("How does randomized Quicksort choose its pivot?")

    assert answer.status == "abstained"
    assert answer.claims == []
    assert answer.sources == []
    assert reranker.calls == 0
    assert provider.calls == 0
