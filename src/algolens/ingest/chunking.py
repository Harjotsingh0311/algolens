from __future__ import annotations

import html
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

PAGE_MARKER_RE = re.compile(r"(?m)^\s*<!--\s*source_page:\s*(\d+)\s*-->\s*$")
WORD_RE = re.compile(r"\b[\w’'-]+\b", re.UNICODE)
HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$")
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
HTML_BREAK_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
UNDERLINE_TAG_RE = re.compile(r"</?u\s*>", re.IGNORECASE)
PAGE_FURNITURE_LINES = {
    "randomized algorithms 6.046j spring 2015",
    "randomized algorithms",
    "6.046j spring 2015",
    "lecture 6",
}
PAGE_NUMBER_RE = re.compile(r"^[1-7]$")


def _is_page_furniture(line: str) -> bool:
    normalized = " ".join(line.split()).casefold()
    return normalized in PAGE_FURNITURE_LINES or bool(PAGE_NUMBER_RE.fullmatch(normalized))


@dataclass(frozen=True)
class TextUnit:
    """Small source passage with its original locator."""

    text: str
    page: int | None = None
    section: str | None = None
    start: float | None = None
    end: float | None = None


def word_count(text: str) -> int:
    """Count approximate words consistently for chunk sizing."""
    return len(WORD_RE.findall(text))


def _clean_heading(text: str) -> str:
    text = re.sub(r"^\s{0,3}#{1,6}\s+", "", text)
    text = re.sub(r"[*_`]", "", text)
    return text.strip().rstrip("#").strip()


def _split_large_unit(unit: TextUnit, max_words: int) -> list[TextUnit]:
    """Split exceptionally long lines while retaining their source locator."""
    if word_count(unit.text) <= max_words:
        return [unit]

    words = unit.text.split()
    return [
        TextUnit(
            text=" ".join(words[index : index + max_words]),
            page=unit.page,
            section=unit.section,
            start=unit.start,
            end=unit.end,
        )
        for index in range(0, len(words), max_words)
    ]


def parse_pdf_markdown(markdown: str) -> list[TextUnit]:
    """Parse explicit source_page markers and retain section headings."""
    markers = list(PAGE_MARKER_RE.finditer(markdown))
    if not markers:
        raise ValueError("PDF Markdown contains no source_page markers.")

    units: list[TextUnit] = []
    current_section: str | None = None

    for index, marker in enumerate(markers):
        page_number = int(marker.group(1))
        body_start = marker.end()
        body_end = markers[index + 1].start() if index + 1 < len(markers) else len(markdown)
        page_body = markdown[body_start:body_end]

        for raw_line in page_body.splitlines():
            line = html.unescape(raw_line)
            line = HTML_BREAK_RE.sub("\n", line)
            line = HTML_COMMENT_RE.sub("", line)
            line = UNDERLINE_TAG_RE.sub("", line)

            for part in line.splitlines():
                clean_line = part.strip()
                if not clean_line or _is_page_furniture(clean_line):
                    continue

                heading_match = HEADING_RE.match(clean_line)
                if heading_match:
                    current_section = _clean_heading(heading_match.group(1))
                    continue

                unit = TextUnit(
                    text=clean_line,
                    page=page_number,
                    section=current_section,
                )
                units.extend(_split_large_unit(unit, max_words=200))

    if not units:
        raise ValueError("No text passages found in page-aware PDF Markdown.")

    return units


def filter_pdf_quicksort_units(units: Sequence[TextUnit]) -> list[TextUnit]:
    """Keep Quicksort and its related analysis sections only."""
    retained = [
        unit
        for unit in units
        if (
            "quicksort" in (unit.section or "").casefold()
            or (unit.section or "").casefold().strip()
            in {
                "pivot selection using median finding",
                "expectations",
            }
        )
    ]

    if not retained:
        raise ValueError("No Quicksort-related PDF sections were found.")

    return retained


def filter_transcript_from(
    units: Sequence[TextUnit],
    *,
    start_seconds: float,
) -> list[TextUnit]:
    """Keep timestamped transcript cues starting at a chosen boundary."""
    if start_seconds < 0:
        raise ValueError("The transcript start boundary cannot be negative.")

    if any(unit.start is None or unit.end is None for unit in units):
        raise ValueError("Transcript scope filtering requires cue timestamps.")

    retained = [unit for unit in units if unit.start is not None and unit.start >= start_seconds]

    if not retained:
        raise ValueError(f"No transcript cues found at or after {start_seconds:.3f} seconds.")

    return retained


def parse_transcript_jsonl(content: str) -> list[TextUnit]:
    """Parse cue-level timestamped JSONL without inventing word alignment."""
    units: list[TextUnit] = []
    previous_start = -1.0

    for line_number, line in enumerate(content.splitlines(), start=1):
        if not line.strip():
            continue

        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON on transcript line {line_number}: {exc}") from exc

        if not isinstance(record, dict):
            raise ValueError(f"Transcript line {line_number} must contain a JSON object.")

        if not {"start", "end", "text"}.issubset(record):
            raise ValueError(f"Transcript line {line_number} lacks start, end, or text.")

        start_value = record["start"]
        end_value = record["end"]
        text_value = record["text"]

        if (
            isinstance(start_value, bool)
            or not isinstance(start_value, (int, float))
            or isinstance(end_value, bool)
            or not isinstance(end_value, (int, float))
        ):
            raise ValueError(f"Transcript line {line_number} has nonnumeric timestamps.")

        start = float(start_value)
        end = float(end_value)

        if start < 0 or end < start:
            raise ValueError(f"Transcript line {line_number} has an invalid time range.")

        if start < previous_start:
            raise ValueError(f"Transcript timestamps go backwards at line {line_number}.")

        if not isinstance(text_value, str) or not text_value.strip():
            raise ValueError(f"Transcript line {line_number} has empty or invalid text.")

        units.extend(
            _split_large_unit(
                TextUnit(
                    text=text_value.strip(),
                    start=start,
                    end=end,
                ),
                max_words=200,
            )
        )
        previous_start = start

    if not units:
        raise ValueError("Transcript JSONL contains no usable cues.")

    return units


def _group_word_count(units: Sequence[TextUnit]) -> int:
    return word_count("\n".join(unit.text for unit in units))


def group_units(
    units: Sequence[TextUnit],
    *,
    target_words: int,
    min_words: int,
    max_words: int,
) -> list[list[TextUnit]]:
    """Group source passages without exceeding the requested word maximum.

    Where possible, a short final group is balanced by moving whole passages
    from the preceding group. A small final group is allowed when a larger
    final group would violate the maximum size or other boundaries.
    """
    if not 1 <= min_words <= target_words <= max_words:
        raise ValueError("Require 1 <= min_words <= target_words <= max_words.")

    expanded: list[TextUnit] = []
    for unit in units:
        expanded.extend(_split_large_unit(unit, max_words=max_words))

    groups: list[list[TextUnit]] = []
    current: list[TextUnit] = []
    current_words = 0

    for unit in expanded:
        unit_words = word_count(unit.text)

        if unit_words == 0:
            continue
        if unit_words > max_words:
            raise ValueError("An indivisible unit exceeds max_words.")

        if current and current_words + unit_words > max_words:
            groups.append(current)
            current = []
            current_words = 0

        current.append(unit)
        current_words += unit_words

        if current_words >= target_words:
            groups.append(current)
            current = []
            current_words = 0

    if current:
        groups.append(current)

    # Rebalance the final group when a safe move can improve its size.
    if len(groups) > 1:
        tail = groups[-1]
        previous = groups[-2]

        while _group_word_count(tail) < min_words and len(previous) > 1:
            candidate = previous[-1]
            candidate_words = word_count(candidate.text)
            previous_after_move = _group_word_count(previous) - candidate_words

            if previous_after_move < min_words:
                break
            if _group_word_count(tail) + candidate_words > max_words:
                break

            tail.insert(0, previous.pop())

    for group in groups:
        if _group_word_count(group) > max_words:
            raise ValueError("Generated a group exceeding max_words.")

    return groups


def _unique_sections(units: Sequence[TextUnit]) -> list[str]:
    sections: list[str] = []
    for unit in units:
        if unit.section and unit.section not in sections:
            sections.append(unit.section)
    return sections


def _format_timestamp(seconds: float) -> str:
    milliseconds = round(seconds * 1000)
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    whole_seconds, milliseconds = divmod(remainder, 1000)

    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d}.{milliseconds:03d}"


def _locator(units: Sequence[TextUnit]) -> dict[str, Any]:
    pages = sorted({unit.page for unit in units if unit.page is not None})
    timed_units = [unit for unit in units if unit.start is not None and unit.end is not None]

    if pages and timed_units:
        raise ValueError("A chunk cannot mix PDF pages and video timestamps.")

    if pages:
        first_page = pages[0]
        last_page = pages[-1]
        display = f"p. {first_page}" if first_page == last_page else f"pp. {first_page}–{last_page}"
        return {
            "kind": "pdf_page",
            "pages": pages,
            "page_start": first_page,
            "page_end": last_page,
            "timestamp_start_seconds": None,
            "timestamp_end_seconds": None,
            "display": display,
        }

    if timed_units:
        start = timed_units[0].start
        end = timed_units[-1].end

        if start is None or end is None:
            raise ValueError("Timestamp locator is unexpectedly incomplete.")

        return {
            "kind": "video_timestamp",
            "pages": [],
            "page_start": None,
            "page_end": None,
            "timestamp_start_seconds": start,
            "timestamp_end_seconds": end,
            "display": (f"{_format_timestamp(start)}–{_format_timestamp(end)}"),
        }

    raise ValueError("Chunk has neither page nor timestamp provenance.")


def _make_chunk_record(
    units: Sequence[TextUnit],
    *,
    source_record: Mapping[str, Any],
    source_path: str,
    artifact_sha256: str,
    review_status: str,
    chunk_id: str,
    level: str,
    parent_id: str | None,
    ordinal: int,
    child_ids: list[str] | None = None,
) -> dict[str, Any]:
    text = "\n".join(unit.text for unit in units).strip()
    locator = _locator(units)
    sections = _unique_sections(units)

    source_id = str(source_record["id"])
    lecture = source_record.get("lecture", "unknown")
    context_parts = [
        f"MIT 6.046J Lecture {lecture}",
        f"Source ID: {source_id}",
    ]

    if sections:
        context_parts.append("Sections: " + " > ".join(sections[:3]))

    context_parts.append(str(locator["display"]))
    context_header = " | ".join(context_parts)

    result: dict[str, Any] = {
        "schema_version": 1,
        "chunk_id": chunk_id,
        "level": level,
        "parent_id": parent_id,
        "ordinal": ordinal,
        "source_id": source_id,
        "source_type": source_record.get("type"),
        "source_url": source_record.get("url"),
        "source_path": source_path,
        "source_sha256": source_record.get("sha256"),
        "artifact_sha256": artifact_sha256,
        "licence": source_record.get("licence"),
        "tier": source_record.get("tier"),
        "trust": source_record.get("trust"),
        "scope": source_record.get("scope"),
        "source_status": source_record.get("status"),
        "review_status": review_status,
        "context_header": context_header,
        "retrieval_text": f"{context_header}\n\n{text}",
        "text": text,
        "word_count": word_count(text),
        "pages": locator["pages"],
        "page_start": locator["page_start"],
        "page_end": locator["page_end"],
        "timestamp_start_seconds": locator["timestamp_start_seconds"],
        "timestamp_end_seconds": locator["timestamp_end_seconds"],
        "citation": {
            "kind": locator["kind"],
            "display": locator["display"],
            "pages": locator["pages"],
            "page_start": locator["page_start"],
            "page_end": locator["page_end"],
            "start_seconds": locator["timestamp_start_seconds"],
            "end_seconds": locator["timestamp_end_seconds"],
        },
        "sections": sections,
        "section_start": sections[0] if sections else None,
        "section_end": sections[-1] if sections else None,
    }

    if child_ids is not None:
        result["child_ids"] = child_ids

    return result


def build_hierarchical_chunks(
    units: Sequence[TextUnit],
    source_record: Mapping[str, Any],
    *,
    source_path: str,
    artifact_sha256: str,
    review_status: str,
    parent_target_words: int = 480,
    parent_min_words: int = 400,
    parent_max_words: int = 600,
    child_target_words: int = 160,
    child_min_words: int = 120,
    child_max_words: int = 200,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Build parent and child chunks with shared source provenance."""
    parent_groups = group_units(
        units,
        target_words=parent_target_words,
        min_words=parent_min_words,
        max_words=parent_max_words,
    )

    parents: list[dict[str, Any]] = []
    children: list[dict[str, Any]] = []
    source_id = str(source_record["id"])

    for parent_index, parent_units in enumerate(parent_groups, start=1):
        parent_id = f"{source_id}-parent-{parent_index:04d}"

        child_groups = group_units(
            parent_units,
            target_words=child_target_words,
            min_words=child_min_words,
            max_words=child_max_words,
        )
        child_ids = [f"{parent_id}-child-{index:04d}" for index in range(1, len(child_groups) + 1)]

        parents.append(
            _make_chunk_record(
                parent_units,
                source_record=source_record,
                source_path=source_path,
                artifact_sha256=artifact_sha256,
                review_status=review_status,
                chunk_id=parent_id,
                level="parent",
                parent_id=None,
                ordinal=parent_index,
                child_ids=child_ids,
            )
        )

        for child_index, child_units in enumerate(child_groups, start=1):
            children.append(
                _make_chunk_record(
                    child_units,
                    source_record=source_record,
                    source_path=source_path,
                    artifact_sha256=artifact_sha256,
                    review_status=review_status,
                    chunk_id=child_ids[child_index - 1],
                    level="child",
                    parent_id=parent_id,
                    ordinal=child_index,
                )
            )

    return parents, children
