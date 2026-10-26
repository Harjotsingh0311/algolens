import re
from dataclasses import dataclass


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
