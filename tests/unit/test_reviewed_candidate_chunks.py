from __future__ import annotations

from algolens.ingest.reviewed_candidate import build_reviewed_candidate_chunks
from algolens.retrieval.bm25 import is_answer_eligible

SAMPLE = r"""
# Expectations — corrected transcription candidate

## Provenance

Project owner approval: approved.

## Printed page 5 — Expected work and retry count

A good pivot occurs with probability greater than \(1/2\).
The expected number of attempts is at most \(2\).

\[
E[\#\text{iterations}] \leq 2.
\]

## Printed page 6 — Recurrence and recursion tree

\[
T(n) \leq T(n/4) + T(3n/4) + 2cn.
\]

The height is at most \(\log_{4/3}(2cn)\).

\[
T(n) = \Theta(n \log n).
\]

## Transcription and review notes

This material must not be retrieved as evidence.
"""


def source_record() -> dict[str, object]:
    return {
        "id": "L06_TYPED_NOTES",
        "lecture": 6,
        "type": "typed_notes_pdf",
        "url": "https://example.invalid/lecture.pdf",
        "licence": "CC BY-NC-SA 4.0",
        "sha256": "a" * 64,
        "tier": 1,
        "trust": "primary",
        "scope": "randomized_quicksort",
        "status": "downloaded_hash_pinned",
    }


def build():
    return build_reviewed_candidate_chunks(
        SAMPLE,
        source_record(),
        source_path=("corpus/processed/reviewed_candidates/expectations_printed_pages_5_6.md"),
        artifact_sha256="b" * 64,
    )


def test_chunks_keep_pages_separate() -> None:
    parents, children = build()

    assert {tuple(chunk["pages"]) for chunk in parents + children} == {
        (5,),
        (6,),
    }


def test_chunks_preserve_citations_and_provenance_hashes() -> None:
    parents, children = build()

    for chunk in parents + children:
        assert chunk["citation"]["kind"] == "pdf_page"
        assert chunk["source_sha256"] == "a" * 64
        assert chunk["artifact_sha256"] == "b" * 64
        assert chunk["source_path"].endswith("expectations_printed_pages_5_6.md")

    assert {child["citation"]["display"] for child in children} == {
        "p. 5",
        "p. 6",
    }


def test_reviewed_chunks_remain_ineligible_for_answer_generation() -> None:
    parents, children = build()

    for chunk in parents + children:
        assert chunk["review_status"] == "approved_retrieval_disabled"
        assert is_answer_eligible(chunk) is False


def test_parent_child_links_and_text_reconstruction() -> None:
    parents, children = build()
    children_by_parent: dict[str, list[dict[str, object]]] = {}

    for child in children:
        parent_id = str(child["parent_id"])
        children_by_parent.setdefault(parent_id, []).append(child)

    for parent in parents:
        linked = sorted(
            children_by_parent[parent["chunk_id"]],
            key=lambda item: int(item["ordinal"]),
        )
        assert [item["chunk_id"] for item in linked] == parent["child_ids"]
        assert "\n".join(str(item["text"]) for item in linked) == parent["text"]


def test_provenance_and_review_notes_are_not_chunked() -> None:
    parents, children = build()
    combined = "\n".join(str(chunk["text"]) for chunk in parents + children).casefold()

    assert "project owner approval" not in combined
    assert "transcription and review notes" not in combined
    assert "must not be retrieved as evidence" not in combined
