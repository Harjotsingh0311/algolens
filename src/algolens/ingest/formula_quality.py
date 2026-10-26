from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FormulaWarning:
    """A suspicious extraction passage requiring source-PDF review."""

    source_page: int | None
    line_number: int
    pattern: str
    text: str


_PAGE_MARKER = re.compile(r"<!--\s*source_page:\s*(\d+)\s*-->")

_KNOWN_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "matrix-product probability fraction may be malformed",
        re.compile(
            r"Pr\s*\[\s*output\s*=\s*YES\s*\].{0,80}"
            r"(?:≤|<=)\s*(?:12\b|1\s+2\b)",
            re.I,
        ),
    ),
    (
        "good-pivot three-quarter bound may be malformed by HTML layout",
        re.compile(
            r"Good pivot:.{0,220}"
            r"(?:≤|<=)_?.{0,100}3.{0,80}4",
            re.I,
        ),
    ),
    (
        "Quicksort recurrence may have malformed quarter-bound layout",
        re.compile(
            r"T\s*\(\s*n\s*\).{0,180}"
            r"max\s*n?\s*/?\s*_?\s*4.{0,220}"
            r"3\s*_?\s*n?\s*/?\s*_?\s*4",
            re.I,
        ),
    ),
    (
        "Quicksort recurrence may have lost recursive arguments",
        re.compile(
            r"T\s*\(\s*n\s*\)\s*(?:≤|<=)\s*T\s*\+\s*T\s*\+\s*2\s*c\s*n",
            re.I,
        ),
    ),
    (
        "actual extracted Quicksort recurrence layout needs review",
        re.compile(
            r"T.{0,100}maxn/.{0,80}4.{0,100}3.{0,80}n/.{0,80}4",
            re.I,
        ),
    ),
)


def find_formula_warnings(markdown: str) -> list[FormulaWarning]:
    """Return known corruption warnings while preserving source-page context."""
    warnings: list[FormulaWarning] = []
    current_page: int | None = None

    for line_number, line in enumerate(markdown.splitlines(), start=1):
        page_match = _PAGE_MARKER.search(line)
        if page_match:
            current_page = int(page_match.group(1))
            continue

        stripped = line.strip()
        if not stripped:
            continue

        for description, pattern in _KNOWN_PATTERNS:
            if pattern.search(stripped):
                warnings.append(
                    FormulaWarning(
                        source_page=current_page,
                        line_number=line_number,
                        pattern=description,
                        text=stripped[:300],
                    )
                )

    return warnings


def main(argv: Sequence[str] | None = None) -> int:
    """Audit an extracted Markdown file for known formula-corruption patterns."""
    parser = argparse.ArgumentParser(
        description=(
            "Find known mathematical PDF-extraction defects. "
            "Warnings require human review; this tool never edits the source."
        )
    )
    default_path = (
        Path.cwd() / "corpus" / "experiments" / "pdf_extraction" / "notes.md"
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=default_path,
        help="Markdown file to inspect (default: ./corpus/experiments/pdf_extraction/notes.md).",
    )
    parser.add_argument(
        "--fail-on-warning",
        action="store_true",
        help="Return exit code 1 if any known corruption pattern is detected.",
    )
    args = parser.parse_args(argv)

    try:
        markdown = args.path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        print(f"Formula audit could not read {args.path}: {exc}", file=sys.stderr)
        return 2

    warnings = find_formula_warnings(markdown)
    print(f"File: {args.path}")
    print(f"Warnings found: {len(warnings)}")
    for warning in warnings:
        page = (
            f"PDF page {warning.source_page}"
            if warning.source_page is not None
            else "PDF page unknown"
        )
        print(f"[REVIEW] {page}, Markdown line {warning.line_number}: {warning.pattern}")
        print(f"  {warning.text}")

    if not warnings:
        print("No known corruption signatures detected.")
    if warnings and args.fail_on_warning:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
