import json
from pathlib import Path

import pytest

from algolens.ingest.transcript import (
    TranscriptParseError,
    convert_vtt_to_jsonl,
    parse_vtt,
)


def test_parse_vtt_preserves_timestamps_and_multiline_text() -> None:
    content = (
        "WEBVTT\n"
        "Kind: captions\n"
        "Language: en\n"
        "\n"
        "00:00:00.000 --> 00:00:01.500\n"
        "Hello\n"
        "world.\n"
        "\n"
        "00:00:02.000 --> 00:00:03.000\n"
        "Second cue!\n"
    )

    records = parse_vtt(content)

    assert records == [
        {"start": 0.0, "end": 1.5, "text": "Hello world."},
        {"start": 2.0, "end": 3.0, "text": "Second cue!"},
    ]


def test_parse_vtt_removes_basic_markup_and_decodes_entities() -> None:
    content = (
        "WEBVTT\n\n"
        "cue-1\n"
        "00:00:01.000 --> 00:00:02.000 align:start\n"
        "<b>Quicksort</b> &amp; partition\n"
    )

    records = parse_vtt(content)

    assert records == [{"start": 1.0, "end": 2.0, "text": "Quicksort & partition"}]


def test_parse_vtt_rejects_backwards_timestamps() -> None:
    content = (
        "WEBVTT\n\n"
        "00:00:05.000 --> 00:00:06.000\n"
        "First.\n\n"
        "00:00:04.000 --> 00:00:04.500\n"
        "Second.\n"
    )

    with pytest.raises(TranscriptParseError, match="backwards"):
        parse_vtt(content)


def test_parse_vtt_rejects_gaps_over_30_seconds() -> None:
    content = (
        "WEBVTT\n\n"
        "00:00:00.000 --> 00:00:01.000\n"
        "First.\n\n"
        "00:00:40.000 --> 00:00:41.000\n"
        "Second.\n"
    )

    with pytest.raises(TranscriptParseError, match="30 seconds"):
        parse_vtt(content)


def test_parse_vtt_rejects_missing_timestamp_cues() -> None:
    with pytest.raises(TranscriptParseError, match="timestamp"):
        parse_vtt("WEBVTT\n\nThis file has no timed cues.\n")


def test_convert_vtt_to_jsonl_writes_one_record_per_line(
    tmp_path: Path,
) -> None:
    source = tmp_path / "captions.vtt"
    destination = tmp_path / "transcript.jsonl"

    source.write_text(
        "WEBVTT\n\n"
        "00:00:00.000 --> 00:00:01.000\n"
        "Randomized Quicksort.\n\n"
        "00:00:01.500 --> 00:00:02.000\n"
        "Choose a pivot.\n",
        encoding="utf-8",
    )

    result = convert_vtt_to_jsonl(source, destination)

    assert result == destination
    lines = destination.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2

    assert [json.loads(line) for line in lines] == [
        {"start": 0.0, "end": 1.0, "text": "Randomized Quicksort."},
        {"start": 1.5, "end": 2.0, "text": "Choose a pivot."},
    ]


def test_conversion_failure_preserves_existing_output(
    tmp_path: Path,
) -> None:
    source = tmp_path / "invalid.vtt"
    destination = tmp_path / "transcript.jsonl"

    source.write_text("This is not WebVTT.", encoding="utf-8")
    destination.write_text("existing verified output\n", encoding="utf-8")

    with pytest.raises(TranscriptParseError):
        convert_vtt_to_jsonl(source, destination)

    assert destination.read_text(encoding="utf-8") == "existing verified output\n"
    assert not destination.with_name(destination.name + ".part").exists()
