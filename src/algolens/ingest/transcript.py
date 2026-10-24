"""Parse timestamped WebVTT captions into validated transcript records."""

from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import TypedDict


class TranscriptRecord(TypedDict):
    """One timestamped transcript cue."""

    start: float
    end: float
    text: str


class TranscriptParseError(ValueError):
    """Raised when transcript content is missing or invalid."""


_TIMESTAMP = r"(?:(?:\d{2,}):)?\d{2}:\d{2}\.\d{3}"

_TIMING_LINE = re.compile(
    rf"^(?P<start>{_TIMESTAMP})\s+-->\s+"
    rf"(?P<end>{_TIMESTAMP})(?:\s+.*)?$"
)

_TAG = re.compile(r"<[^>]*>")
_WHITESPACE = re.compile(r"\s+")


def _timestamp_seconds(value: str) -> float:
    """Convert an HH:MM:SS.mmm or MM:SS.mmm timestamp to seconds."""
    parts = value.split(":")

    try:
        if len(parts) == 3:
            hours, minutes, seconds_part = parts
        elif len(parts) == 2:
            hours = "0"
            minutes, seconds_part = parts
        else:
            raise ValueError("Unexpected timestamp format.")

        seconds, milliseconds = seconds_part.split(".")

        if int(minutes) > 59 or int(seconds) > 59:
            raise ValueError("Minute or second value is outside its valid range.")

        return int(hours) * 3600 + int(minutes) * 60 + int(seconds) + int(milliseconds) / 1000
    except (ValueError, IndexError) as exc:
        raise TranscriptParseError(f"Invalid WebVTT timestamp: {value!r}") from exc


def _clean_text(lines: list[str]) -> str:
    """Remove basic WebVTT/HTML formatting and normalize whitespace."""
    text = " ".join(line.strip() for line in lines)
    text = _TAG.sub("", text)
    text = html.unescape(text)
    return _WHITESPACE.sub(" ", text).strip()


def parse_vtt(content: str) -> list[TranscriptRecord]:
    """Parse WebVTT text while enforcing timestamp order and gap limits."""
    if not content or not content.strip():
        raise TranscriptParseError("Transcript content is empty.")

    normalized = content.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")

    if not normalized.startswith("WEBVTT"):
        raise TranscriptParseError("Input does not start with a WEBVTT header.")

    blocks = re.split(r"\n[ \t]*\n", normalized.strip())
    records: list[TranscriptRecord] = []

    previous_start: float | None = None
    furthest_previous_end: float | None = None

    for block_number, block in enumerate(blocks, start=1):
        lines = block.splitlines()
        if not lines:
            continue

        first_line = lines[0].strip()

        if first_line.startswith(("WEBVTT", "NOTE", "STYLE", "REGION")):
            continue

        timing_index: int | None = None
        timing_match: re.Match[str] | None = None

        for index, line in enumerate(lines):
            stripped = line.strip()
            match = _TIMING_LINE.fullmatch(stripped)

            if match is not None:
                timing_index = index
                timing_match = match
                break

            if "-->" in stripped:
                raise TranscriptParseError(
                    f"Malformed timestamp cue in block {block_number}: {stripped!r}"
                )

        if timing_match is None or timing_index is None:
            continue

        start = _timestamp_seconds(timing_match.group("start"))
        end = _timestamp_seconds(timing_match.group("end"))

        if start >= end:
            raise TranscriptParseError(f"Cue {block_number}: start must be before end.")

        if previous_start is not None and start < previous_start:
            raise TranscriptParseError(f"Cue {block_number}: timestamp moves backwards.")

        if furthest_previous_end is not None and start - furthest_previous_end > 30:
            raise TranscriptParseError(f"Cue {block_number}: gap between cues exceeds 30 seconds.")

        text = _clean_text(lines[timing_index + 1 :])
        if not text:
            raise TranscriptParseError(f"Cue {block_number}: caption text is empty.")

        records.append({"start": start, "end": end, "text": text})

        previous_start = start
        furthest_previous_end = (
            end if furthest_previous_end is None else max(furthest_previous_end, end)
        )

    if not records:
        raise TranscriptParseError("No valid timestamped transcript cues were found.")

    return records


def convert_vtt_to_jsonl(
    source: str | Path,
    destination: str | Path,
) -> Path:
    """Convert a VTT file into JSONL without corrupting existing output."""
    source_path = Path(source)
    destination_path = Path(destination)

    try:
        content = source_path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise TranscriptParseError(f"Cannot read transcript source '{source_path}': {exc}") from exc

    records = parse_vtt(content)

    temporary_path = destination_path.with_name(destination_path.name + ".part")

    try:
        destination_path.parent.mkdir(parents=True, exist_ok=True)

        with temporary_path.open("w", encoding="utf-8", newline="\n") as output:
            for record in records:
                output.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")

        temporary_path.replace(destination_path)
        return destination_path

    except OSError as exc:
        raise TranscriptParseError(
            f"Cannot write converted transcript '{destination_path}': {exc}"
        ) from exc
    finally:
        temporary_path.unlink(missing_ok=True)
