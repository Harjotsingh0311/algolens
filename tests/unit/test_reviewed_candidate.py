from __future__ import annotations

import pytest

from algolens.ingest.reviewed_candidate import parse_reviewed_candidate

SAMPLE = r"""
# Expectations — corrected transcription candidate

## Provenance

Project owner approval: approved.

## Printed page 5 — Expected work and retry count

A good pivot occurs with probability greater than \(1/2\).
Therefore, the expected number of attempts is at most \(2\).

\[
E[\#\text{iterations}] \leq 2.
\]

The recurrence displayed on the page is:

\[
T(n) \leq
\max_{n/4 \leq i \leq 3n/4}
\left(T(i) + T(n-i)\right)
+ E[\#\text{iterations}] \cdot cn.
\]

## Printed page 6 — Recurrence and recursion tree

Substituting the expected-attempt bound gives:

\[
T(n) \leq T(n/4) + T(3n/4) + 2cn.
\]

The height is at most \(\log_{4/3}(2cn)\), and the expected runtime is:

\[
T(n) = \Theta(n \log n).
\]

## Transcription and review notes

This section is for human review and must not enter evidence chunks.
"""


def test_parser_preserves_printed_page_numbers() -> None:
    units = parse_reviewed_candidate(SAMPLE)

    assert units
    assert {unit.page for unit in units} == {5, 6}
    assert all(unit.start is None and unit.end is None for unit in units)


def test_parser_keeps_expectations_section_context() -> None:
    units = parse_reviewed_candidate(SAMPLE)

    assert all(unit.section == "Expectations" for unit in units)


def test_parser_preserves_key_equations() -> None:
    units = parse_reviewed_candidate(SAMPLE)
    combined = "\n".join(unit.text for unit in units)

    assert r"E[\#\text{iterations}] \leq 2" in combined
    assert r"\max_{n/4 \leq i \leq 3n/4}" in combined
    assert r"T(n) \leq T(n/4) + T(3n/4) + 2cn" in combined
    assert r"\log_{4/3}(2cn)" in combined
    assert r"T(n) = \Theta(n \log n)" in combined


def test_parser_excludes_provenance_and_review_notes() -> None:
    units = parse_reviewed_candidate(SAMPLE)
    combined = "\n".join(unit.text for unit in units).casefold()

    assert "project owner approval" not in combined
    assert "transcription and review notes" not in combined
    assert "must not enter evidence chunks" not in combined


def test_parser_rejects_missing_printed_page() -> None:
    incomplete = SAMPLE.replace(
        "## Printed page 6 — Recurrence and recursion tree",
        "## Printed page 7 — Recurrence and recursion tree",
    )

    with pytest.raises(ValueError):
        parse_reviewed_candidate(incomplete)
