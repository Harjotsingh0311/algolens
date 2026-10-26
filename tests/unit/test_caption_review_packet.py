from __future__ import annotations

import pytest

from tools.create_caption_review_packet import (
    CaptionCue,
    build_review_packet,
    parse_cues,
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
        CaptionCue("00:00:01.000", "00:00:02.000", "Hello welcome"),
        CaptionCue("00:00:03.000", "00:00:04.000", "Second cue"),
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
