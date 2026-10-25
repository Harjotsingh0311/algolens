from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest

from algolens.answer_cache import CachedAnswerProvider
from algolens.answering import AnswerDraft
from algolens.contracts import CitationReference, Claim, Hit, Passage


class FakeProvider:
    def __init__(
        self,
        result: AnswerDraft | Mapping[str, Any] | None = None,
        *,
        error: Exception | None = None,
    ) -> None:
        self.result = (
            result
            if result is not None
            else AnswerDraft(
                answer_md="Randomized Quicksort chooses a pivot at random [p. 5].",
                claims=[
                    Claim(
                        text="Randomized Quicksort chooses a pivot at random.",
                        cites=["passage-001"],
                        support="supported",
                    )
                ],
            )
        )
        self.error = error
        self.calls = 0

    def generate(
        self,
        question: str,
        evidence: Sequence[Hit],
        *,
        allow_partial: bool,
    ) -> AnswerDraft | Mapping[str, Any]:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.result


def make_hit(
    *,
    passage_id: str = "passage-001",
    text: str = "Randomized Quicksort chooses a pivot at random.",
    review_status: str = "reviewed",
    eligible_for_answer: bool = True,
    score: float = 2.5,
) -> Hit:
    passage = Passage(
        id=passage_id,
        lecture=6,
        kind="notes",
        text=text,
        section="Randomized Quicksort",
        page=5,
        citation=CitationReference(
            kind="pdf_page",
            display="p. 5",
            page_start=5,
            page_end=5,
        ),
        source_id="L06_TYPED_NOTES",
        source_sha256="a" * 64,
        review_status=review_status,
        eligible_for_answer=eligible_for_answer,
    )
    return Hit(passage=passage, score=score, ranks={"hybrid": 1})


def build_cache(
    provider: FakeProvider,
    path: Path,
    *,
    corpus_version: str = "corpus-v1",
    model_id: str = "test-model",
) -> CachedAnswerProvider:
    return CachedAnswerProvider(
        provider,
        corpus_version=corpus_version,
        model_id=model_id,
        cache_path=path,
    )


def test_identical_question_model_corpus_and_evidence_reuse_cached_draft(tmp_path: Path) -> None:
    provider = FakeProvider()
    cache = build_cache(provider, tmp_path / "cache.sqlite3")
    evidence = [make_hit()]
    question = "How does randomized Quicksort choose its pivot?"

    first = cache.generate(question, evidence, allow_partial=False)
    second = cache.generate(question, evidence, allow_partial=False)

    assert first.model_dump() == second.model_dump()
    assert provider.calls == 1
    assert (tmp_path / "cache.sqlite3").is_file()


@pytest.mark.parametrize(
    ("corpus_version", "model_id"),
    [
        ("corpus-v2", "test-model"),
        ("corpus-v1", "different-model"),
    ],
)
def test_cache_is_namespaced_by_corpus_and_model(
    tmp_path: Path,
    corpus_version: str,
    model_id: str,
) -> None:
    path = tmp_path / "cache.sqlite3"
    first_provider = FakeProvider()
    build_cache(first_provider, path).generate("Question?", [make_hit()], allow_partial=False)

    second_provider = FakeProvider()
    build_cache(
        second_provider,
        path,
        corpus_version=corpus_version,
        model_id=model_id,
    ).generate("Question?", [make_hit()], allow_partial=False)

    assert first_provider.calls == 1
    assert second_provider.calls == 1


def test_evidence_text_and_partial_mode_are_part_of_the_cache_key(tmp_path: Path) -> None:
    provider = FakeProvider()
    cache = build_cache(provider, tmp_path / "cache.sqlite3")

    cache.generate("Question?", [make_hit()], allow_partial=False)
    cache.generate(
        "Question?",
        [make_hit(text="A revised, explicitly approved passage.")],
        allow_partial=False,
    )
    cache.generate("Question?", [make_hit()], allow_partial=True)

    assert provider.calls == 3


def test_failed_generation_is_not_cached(tmp_path: Path) -> None:
    provider = FakeProvider(error=RuntimeError("temporary provider outage"))
    cache = build_cache(provider, tmp_path / "cache.sqlite3")
    evidence = [make_hit()]

    with pytest.raises(RuntimeError, match="temporary provider outage"):
        cache.generate("Question?", evidence, allow_partial=False)

    provider.error = None
    cache.generate("Question?", evidence, allow_partial=False)

    assert provider.calls == 2


def test_unapproved_evidence_is_rejected_before_cache_or_provider(tmp_path: Path) -> None:
    provider = FakeProvider()
    cache = build_cache(provider, tmp_path / "cache.sqlite3")
    unapproved = make_hit(
        review_status="approved_retrieval_disabled",
        eligible_for_answer=False,
    )

    with pytest.raises(ValueError, match="approved evidence"):
        cache.generate("Question?", [unapproved], allow_partial=False)

    assert provider.calls == 0
    assert not (tmp_path / "cache.sqlite3").exists()


def test_draft_with_unknown_citation_is_not_cached(tmp_path: Path) -> None:
    provider = FakeProvider(
        AnswerDraft(
            answer_md="An answer.",
            claims=[
                Claim(
                    text="An unsupported reference.",
                    cites=["missing-passage"],
                    support="supported",
                )
            ],
        )
    )
    cache = build_cache(provider, tmp_path / "cache.sqlite3")
    evidence = [make_hit()]

    with pytest.raises(ValueError, match="absent from supplied evidence"):
        cache.generate("Question?", evidence, allow_partial=False)

    provider.result = AnswerDraft(
        answer_md="A corrected answer [p. 5].",
        claims=[
            Claim(
                text="A correct claim.",
                cites=["passage-001"],
                support="supported",
            )
        ],
    )
    cache.generate("Question?", evidence, allow_partial=False)

    assert provider.calls == 2


def test_expired_entry_is_regenerated(tmp_path: Path) -> None:
    import sqlite3
    import time

    path = tmp_path / "cache.sqlite3"
    provider = FakeProvider()
    cache = build_cache(provider, path)
    cache.generate("Question?", [make_hit()], allow_partial=False)

    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE answer_cache SET created_at = ?",
            (time.time() - 10_000,),
        )

    cache.generate("Question?", [make_hit()], allow_partial=False)
    assert provider.calls == 2
