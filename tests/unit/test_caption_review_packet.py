from __future__ import annotations

import sys
from pathlib import Path

import pytest

from tools.create_caption_review_packet import (
    CaptionCue,
    build_review_packet,
    parse_cues,
    main,
)


def test_parse_cues_preserves_timestamps_and_cleans_markup() -> None:
    raw = (
        "WEBVTT\n\n"
        "00:00:01.000 --> 00:00:02.000\n"
        "<c.green>Hello &amp; welcome</c>\n\n"
        "00:00:03.000 --> 00:00:04.000\n"
        "Second cue\n"
    )

    assert parse_cues(raw) == [
        CaptionCue("00:00:01.000", "00:00:02.000", "Hello & welcome"),
        CaptionCue("00:00:03.000", "00:00:04.000", "Second cue"),
    ]


def test_parse_cues_decodes_common_html_entities() -> None:
    raw = (
        "WEBVTT\n\n"
        "00:00:01.000 --> 00:00:02.000\n"
        "A &amp; B &lt; C &gt; D &nbsp; E\n"
    )
    assert parse_cues(raw) == [
        CaptionCue("00:00:01.000", "00:00:02.000", "A & B < C > D E")
    ]


def test_review_packet_is_reproducible_and_explicitly_pending() -> None:
    cues = [
        CaptionCue(f"00:00:{second:02d}.000", f"00:00:{second + 1:02d}.000", f"Cue {second}")
        for second in range(20)
    ]

    first = build_review_packet(cues, count=5, seed=77)
    second = build_review_packet(cues, count=5, seed=77)

    assert first == second
    assert first.count("| Pending |") == 5
    assert "PENDING HUMAN REVIEW" in first
    assert "does not approve the corpus" in first
    assert "Do not change canonical passage eligibility" in first


@pytest.mark.parametrize(
    ("cues", "count"),
    [([], 1), ([CaptionCue("00:00:00.000", "00:00:01.000", "Only")], 0)],
)
def test_review_packet_rejects_invalid_input(cues: list[CaptionCue], count: int) -> None:
    with pytest.raises(ValueError):
        build_review_packet(cues, count=count)


def test_review_packet_rejects_more_samples_than_available() -> None:
    cues = [CaptionCue("00:00:00.000", "00:00:01.000", "Only")]
    with pytest.raises(ValueError, match="only 1 non-empty cues"):
        build_review_packet(cues, count=2)



def test_cli_refuses_to_overwrite_existing_review_packet(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "captions.vtt"
    output = tmp_path / "review.md"
    source.write_text(
        "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nHello\n",
        encoding="utf-8",
    )
    output.write_text("human review notes", encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        ["create_caption_review_packet", "--input", str(source), "--output", str(output)],
    )

    with pytest.raises(SystemExit, match="refusing to overwrite reviewer work"):
        main()
    assert output.read_text(encoding="utf-8") == "human review notes"
