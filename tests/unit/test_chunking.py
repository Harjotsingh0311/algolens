from __future__ import annotations

import json

import pytest

from algolens.ingest.chunking import (
    TextUnit,
    build_hierarchical_chunks,
    filter_pdf_quicksort_units,
    filter_transcript_from,
    group_units,
    parse_pdf_markdown,
    parse_transcript_jsonl,
)


def test_pdf_parser_preserves_pages_and_sections() -> None:
    markdown = """<!-- source_page: 1 -->
# **Introduction**
Introductory passage.
<!-- Start of picture text -->
A × B<br><!-- End of picture text -->
<!-- source_page: 2 -->
## **Quicksort**
A second passage.
"""

    units = parse_pdf_markdown(markdown)

    assert [unit.page for unit in units] == [1, 1, 2]
    assert units[0].section == "Introduction"
    assert units[1].text == "A × B"
    assert units[1].section == "Introduction"
    assert units[2].section == "Quicksort"
    assert all("source_page" not in unit.text for unit in units)


def test_pdf_parser_requires_explicit_page_markers() -> None:
    with pytest.raises(ValueError, match="no source_page markers"):
        parse_pdf_markdown("# No provenance here\nSome text.")


def test_transcript_parser_preserves_cue_timestamps() -> None:
    content = "\n".join(
        [
            json.dumps({"start": 0.09, "end": 2.5, "text": "First cue."}),
            json.dumps({"start": 2.5, "end": 4.25, "text": "Second cue."}),
        ]
    )

    units = parse_transcript_jsonl(content)

    assert len(units) == 2
    assert units[0].start == 0.09
    assert units[0].end == 2.5
    assert units[1].start == 2.5
    assert units[1].end == 4.25


def test_transcript_parser_rejects_backwards_timestamps() -> None:
    content = "\n".join(
        [
            json.dumps({"start": 3, "end": 4, "text": "First."}),
            json.dumps({"start": 2, "end": 5, "text": "Second."}),
        ]
    )

    with pytest.raises(ValueError, match="go backwards"):
        parse_transcript_jsonl(content)


def test_group_units_preserves_text_and_respects_maximum() -> None:
    units = [
        TextUnit(
            text=" ".join([f"word{index}"] * 15),
            page=1,
            section="Test",
        )
        for index in range(20)
    ]

    groups = group_units(
        units,
        target_words=60,
        min_words=45,
        max_words=75,
    )

    assert len(groups) > 1
    assert all(sum(len(unit.text.split()) for unit in group) <= 75 for group in groups)

    original_text = "\n".join(unit.text for unit in units)
    grouped_text = "\n".join("\n".join(unit.text for unit in group) for group in groups)
    assert grouped_text == original_text


def test_hierarchical_chunks_preserve_page_citations_and_links() -> None:
    record = {
        "id": "L06_TYPED_NOTES",
        "lecture": 6,
        "type": "typed_notes_pdf",
        "url": "https://example.invalid/lecture.pdf",
        "licence": "CC BY-NC-SA 4.0",
        "sha256": "a" * 64,
        "tier": 1,
        "trust": "primary",
        "scope": "randomized_quicksort",
        "status": "review_pending",
    }

    units = [
        TextUnit(
            text=" ".join([f"term{index}"] * 10),
            page=(index // 4) + 1,
            section="Quicksort" if index < 8 else "Analysis",
        )
        for index in range(12)
    ]

    parents, children = build_hierarchical_chunks(
        units,
        record,
        source_path="corpus/experiments/notes.md",
        artifact_sha256="b" * 64,
        review_status="unreviewed_extraction",
        parent_target_words=40,
        parent_min_words=30,
        parent_max_words=50,
        child_target_words=20,
        child_min_words=15,
        child_max_words=25,
    )

    assert len(parents) == 3
    assert len(children) == 6
    assert parents[0]["citation"]["kind"] == "pdf_page"
    assert parents[0]["pages"] == [1]
    assert parents[0]["source_sha256"] == "a" * 64
    assert parents[0]["review_status"] == "unreviewed_extraction"

    by_parent: dict[str, list[dict[str, object]]] = {}
    for child in children:
        by_parent.setdefault(str(child["parent_id"]), []).append(child)

    for parent in parents:
        linked = sorted(
            by_parent[parent["chunk_id"]],
            key=lambda item: int(item["ordinal"]),
        )
        assert [item["chunk_id"] for item in linked] == parent["child_ids"]
        assert "\n".join(str(item["text"]) for item in linked) == parent["text"]


def test_transcript_chunks_cite_cue_time_ranges() -> None:
    record = {
        "id": "L06_YOUTUBE_CAPTIONS",
        "lecture": 6,
        "type": "youtube_caption_track",
        "url": "https://www.youtube.com/watch?v=example",
        "licence": "CC BY-NC-SA 4.0",
        "sha256": "c" * 64,
        "tier": 1,
        "trust": "caption_track_pending_spot_check",
        "scope": "randomized_quicksort",
        "status": "content_review_pending",
    }

    units = [
        TextUnit(
            text=" ".join([f"cue{index}"] * 10),
            start=float(index * 10),
            end=float(index * 10 + 2),
        )
        for index in range(12)
    ]

    parents, children = build_hierarchical_chunks(
        units,
        record,
        source_path="corpus/processed/transcript.jsonl",
        artifact_sha256="d" * 64,
        review_status="pending_spot_check",
        parent_target_words=40,
        parent_min_words=30,
        parent_max_words=50,
        child_target_words=20,
        child_min_words=15,
        child_max_words=25,
    )

    assert parents[0]["citation"]["kind"] == "video_timestamp"
    assert parents[0]["timestamp_start_seconds"] == 0.0
    assert parents[0]["timestamp_end_seconds"] == 32.0
    assert children[0]["review_status"] == "pending_spot_check"
    assert children[0]["timestamp_start_seconds"] == 0.0


def test_pdf_parser_removes_repeated_page_furniture() -> None:
    markdown = """<!-- source_page: 1 -->
Randomized Algorithms 6.046J Spring 2015
Lecture 6
# Introduction
Intro text.
1
<!-- source_page: 2 -->
Randomized Algorithms
6.046J Spring 2015
Lecture 6
# Quicksort
Quicksort explanation.
2
"""
    units = parse_pdf_markdown(markdown)

    assert [unit.text for unit in units] == [
        "Intro text.",
        "Quicksort explanation.",
    ]
    assert [unit.page for unit in units] == [1, 2]


def test_pdf_quicksort_filter_excludes_matrix_product() -> None:
    units = [
        TextUnit(
            text="Matrix Product content.",
            page=2,
            section="Matrix Product Checker",
        ),
        TextUnit(
            text="Quicksort content.",
            page=4,
            section="Quicksort",
        ),
        TextUnit(
            text="Pivot-selection content.",
            page=4,
            section="Pivot Selection Using Median Finding",
        ),
        TextUnit(
            text="Expectation analysis.",
            page=6,
            section="Expectations",
        ),
    ]

    selected = filter_pdf_quicksort_units(units)

    assert [unit.text for unit in selected] == [
        "Quicksort content.",
        "Pivot-selection content.",
        "Expectation analysis.",
    ]


def test_transcript_scope_starts_at_the_selected_quicksort_cue() -> None:
    units = [
        TextUnit(
            text="Introductory mention.",
            start=604.560,
            end=605.830,
        ),
        TextUnit(
            text="Quicksort transition.",
            start=2997.340,
            end=3003.039,
        ),
        TextUnit(
            text="Quicksort explanation.",
            start=3024.590,
            end=3029.360,
        ),
    ]

    selected = filter_transcript_from(units, start_seconds=2997.340)

    assert [unit.text for unit in selected] == [
        "Quicksort transition.",
        "Quicksort explanation.",
    ]
    assert selected[0].start == 2997.340
