from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from .chunking import TextUnit, build_hierarchical_chunks

PAGE_HEADING_RE = re.compile(r"^\s*##\s+Printed page\s+(\d+)\s+[—–-]\s+(.+?)\s*$")
REVIEW_NOTES_HEADING = "## Transcription and review notes"
EXPECTED_PAGES = [5, 6]


def _collect_blocks(lines: list[str], page: int) -> list[TextUnit]:
    """Collect prose and display equations while preserving the page number."""
    blocks: list[str] = []
    current: list[str] = []
    in_math = False

    def flush() -> None:
        if current:
            block = " ".join(current).strip()
            if block:
                blocks.append(block)
            current.clear()

    for raw_line in lines:
        line = raw_line.strip()

        if line == r"\[":
            if in_math:
                raise ValueError(f"Nested display-math opener on page {page}.")
            flush()
            in_math = True
            continue

        if line == r"\]":
            if not in_math:
                raise ValueError(f"Unexpected display-math closer on page {page}.")
            flush()
            in_math = False
            continue

        if not line:
            if not in_math:
                flush()
            continue

        if line.startswith("## "):
            raise ValueError(f"Unexpected section heading inside printed page {page}: {line}")

        current.append(line)

    if in_math:
        raise ValueError(f"Unclosed display equation on page {page}.")

    flush()

    return [TextUnit(text=block, page=page, section="Expectations") for block in blocks]


def parse_reviewed_candidate(markdown: str) -> list[TextUnit]:
    """Parse the approved two-page Expectations transcription.

    Only content beneath the printed-page 5 and 6 headings is retained.
    Provenance and transcription-review notes are excluded from evidence.
    This parser does not grant retrieval eligibility.
    """
    if not markdown.strip():
        raise ValueError("Reviewed candidate Markdown is empty.")

    lines = markdown.splitlines()

    page_headings: list[tuple[int, int]] = []
    for index, line in enumerate(lines):
        match = PAGE_HEADING_RE.match(line)
        if match:
            page_headings.append((index, int(match.group(1))))

    pages = [page for _, page in page_headings]
    if pages != EXPECTED_PAGES:
        raise ValueError(f"Expected printed-page headings {EXPECTED_PAGES}, found {pages}.")

    notes_indices = [
        index for index, line in enumerate(lines) if line.strip() == REVIEW_NOTES_HEADING
    ]
    if len(notes_indices) != 1:
        raise ValueError("Expected exactly one 'Transcription and review notes' heading.")

    page5_index = page_headings[0][0]
    page6_index = page_headings[1][0]
    notes_index = notes_indices[0]

    if notes_index <= page6_index:
        raise ValueError("Review notes must follow the printed-page 6 section.")

    page5_lines = lines[page5_index + 1 : page6_index]
    page6_lines = lines[page6_index + 1 : notes_index]

    units = _collect_blocks(page5_lines, page=5)
    units.extend(_collect_blocks(page6_lines, page=6))

    if not units:
        raise ValueError("The reviewed candidate contains no page-level passages.")

    found_pages = sorted({unit.page for unit in units if unit.page is not None})
    if found_pages != EXPECTED_PAGES:
        raise ValueError(f"Expected content from pages {EXPECTED_PAGES}, found {found_pages}.")

    return units


def validate_candidate_metadata(
    metadata: dict[str, object],
    *,
    actual_source_sha256: str,
    actual_candidate_sha256: str,
) -> None:
    """Validate provenance and safety gates for the reviewed transcription.

    Owner approval does not grant retrieval eligibility. Enabling retrieval
    must be a separate, explicit decision after integration and testing.
    """
    source_hash = metadata.get("source_sha256")
    if (
        not isinstance(source_hash, str)
        or source_hash.casefold() != actual_source_sha256.casefold()
    ):
        raise ValueError("source SHA-256 mismatch.")

    candidate_hash = metadata.get("candidate_markdown_sha256")
    if (
        not isinstance(candidate_hash, str)
        or candidate_hash.casefold() != actual_candidate_sha256.casefold()
    ):
        raise ValueError("candidate SHA-256 mismatch.")

    approval = metadata.get("project_owner_approval")
    if not isinstance(approval, str) or approval.strip().casefold() != "approved":
        raise ValueError("Project-owner approval is required.")

    if metadata.get("retrieval_eligible") is not False:
        raise ValueError("retrieval eligibility must remain false during integration.")

    if metadata.get("replaces_original_extraction") is not False:
        raise ValueError("The original extraction must not be replaced.")


def build_reviewed_candidate_chunks(
    markdown: str,
    source_record: Mapping[str, Any],
    *,
    source_path: str,
    artifact_sha256: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Build separately identified chunks for reviewed printed pages 5 and 6.

    Owner approval is recorded in the review metadata. These generated chunks
    remain ineligible for answer generation until a separate retrieval decision.
    """
    if not isinstance(source_path, str) or not source_path.strip():
        raise ValueError("A nonempty reviewed-candidate source path is required.")

    if not re.fullmatch(r"[0-9a-fA-F]{64}", artifact_sha256):
        raise ValueError("The candidate artifact SHA-256 must contain 64 hex characters.")

    source_id_value = source_record.get("id")
    if not isinstance(source_id_value, str) or not source_id_value.strip():
        raise ValueError("The source record must have a nonempty ID.")

    source_id = source_id_value
    units = parse_reviewed_candidate(markdown)
    review_status = "approved_retrieval_disabled"

    all_parents: list[dict[str, Any]] = []
    all_children: list[dict[str, Any]] = []

    # Build each printed page independently. This prevents a parent or child
    # from combining passages whose citation page numbers differ.
    for page in EXPECTED_PAGES:
        page_units = [unit for unit in units if unit.page == page]
        if not page_units:
            raise ValueError(f"No reviewed transcription content for page {page}.")

        parents, children = build_hierarchical_chunks(
            page_units,
            source_record,
            source_path=source_path,
            artifact_sha256=artifact_sha256.lower(),
            review_status=review_status,
        )

        id_map: dict[str, str] = {}
        children_by_parent: dict[str, list[dict[str, Any]]] = {}

        for child in children:
            old_parent_id = str(child["parent_id"])
            children_by_parent.setdefault(old_parent_id, []).append(child)

        for parent in parents:
            old_parent_id = str(parent["chunk_id"])
            new_parent_id = (
                f"{source_id}-reviewed-page-{page:03d}-parent-{int(parent['ordinal']):04d}"
            )
            id_map[old_parent_id] = new_parent_id

            linked_children = sorted(
                children_by_parent.get(old_parent_id, []),
                key=lambda child: int(child["ordinal"]),
            )
            if [child["chunk_id"] for child in linked_children] != parent["child_ids"]:
                raise ValueError(f"Invalid child links for page {page}.")

            for child in linked_children:
                old_child_id = str(child["chunk_id"])
                id_map[old_child_id] = f"{new_parent_id}-child-{int(child['ordinal']):04d}"

        for parent in parents:
            old_parent_id = str(parent["chunk_id"])

            if parent.get("pages") != [page]:
                raise ValueError(f"Parent {old_parent_id} does not have page-specific provenance.")

            parent["chunk_id"] = id_map[old_parent_id]
            parent["child_ids"] = [id_map[str(child_id)] for child_id in parent["child_ids"]]
            parent["review_status"] = review_status
            all_parents.append(parent)

        for child in children:
            old_child_id = str(child["chunk_id"])
            old_parent_id = str(child["parent_id"])

            if child.get("pages") != [page]:
                raise ValueError(f"Child {old_child_id} does not have page-specific provenance.")

            child["chunk_id"] = id_map[old_child_id]
            child["parent_id"] = id_map[old_parent_id]
            child["review_status"] = review_status
            all_children.append(child)

    # Validate parent-child reconstruction after the IDs have been remapped.
    children_by_parent_final: dict[str, list[dict[str, Any]]] = {}
    for child in all_children:
        children_by_parent_final.setdefault(str(child["parent_id"]), []).append(child)

    for parent in all_parents:
        linked = sorted(
            children_by_parent_final.get(str(parent["chunk_id"]), []),
            key=lambda child: int(child["ordinal"]),
        )

        if [child["chunk_id"] for child in linked] != parent["child_ids"]:
            raise ValueError(f"Final child links are invalid for {parent['chunk_id']}.")

        reconstructed = "\n".join(str(child["text"]) for child in linked)
        if reconstructed != parent["text"]:
            raise ValueError(f"Child text does not reconstruct parent {parent['chunk_id']}.")

    return all_parents, all_children
