from pathlib import Path

import pymupdf
import pytest

from algolens.ingest.pdf import PdfExtractionError, extract_pdf_to_markdown


def create_test_pdf(path: Path, page_texts: list[str]) -> None:
    """Create a small local PDF for extraction tests."""
    document = pymupdf.open()

    for text in page_texts:
        page = document.new_page()
        page.insert_text((72, 72), text, fontsize=12)

    document.save(path)
    document.close()


def test_extract_pdf_preserves_page_numbers_and_text(
    tmp_path: Path,
) -> None:
    source = tmp_path / "notes.pdf"
    destination = tmp_path / "notes.md"

    create_test_pdf(
        source,
        [
            "Randomized Quicksort introduction",
            "Expected comparisons E[T] = O(n log n)",
        ],
    )

    result = extract_pdf_to_markdown(source, destination)
    markdown = destination.read_text(encoding="utf-8")

    assert result == destination
    assert "<!-- source_page: 1 -->" in markdown
    assert "<!-- source_page: 2 -->" in markdown
    assert "Randomized Quicksort introduction" in markdown
    assert "Expected comparisons" in markdown
    assert destination.with_name("notes.md.part").exists() is False


def test_invalid_pdf_preserves_existing_output(
    tmp_path: Path,
) -> None:
    source = tmp_path / "invalid.pdf"
    destination = tmp_path / "notes.md"

    source.write_text("This is not a PDF.", encoding="utf-8")
    destination.write_text("previous verified output\n", encoding="utf-8")

    with pytest.raises(PdfExtractionError):
        extract_pdf_to_markdown(source, destination)

    assert destination.read_text(encoding="utf-8") == "previous verified output\n"
    assert destination.with_name("notes.md.part").exists() is False


def test_missing_pdf_raises_clear_error(tmp_path: Path) -> None:
    with pytest.raises(PdfExtractionError, match="Cannot open PDF"):
        extract_pdf_to_markdown(
            tmp_path / "missing.pdf",
            tmp_path / "notes.md",
        )
