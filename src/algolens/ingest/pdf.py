"""Extract PDF content into page-aware Markdown."""

from __future__ import annotations

from pathlib import Path

import pymupdf
import pymupdf4llm  # type: ignore[import-untyped]


class PdfExtractionError(ValueError):
    """Raised when a PDF cannot be opened or extracted safely."""


def extract_pdf_to_markdown(
    source: str | Path,
    destination: str | Path,
) -> Path:
    """Extract Markdown with explicit source-page markers.

    The extracted output is written to a temporary file first. An existing
    destination is replaced only after PDF extraction and writing succeed.
    """
    source_path = Path(source)
    destination_path = Path(destination)

    if not source_path.is_file():
        raise PdfExtractionError(f"Cannot open PDF '{source_path}': source file does not exist.")

    if source_path.resolve() == destination_path.resolve():
        raise PdfExtractionError("PDF source and Markdown destination must be different files.")

    try:
        document = pymupdf.open(str(source_path))  # type: ignore[no-untyped-call]
    except Exception as exc:
        raise PdfExtractionError(f"Cannot open PDF '{source_path}': {exc}") from exc

    try:
        with document:
            if not document.is_pdf:
                raise PdfExtractionError(f"Cannot open PDF '{source_path}': input is not a PDF.")

            if document.page_count < 1:
                raise PdfExtractionError(
                    f"Cannot extract PDF '{source_path}': document has no pages."
                )

            raw_chunks = pymupdf4llm.to_markdown(
                document,
                page_chunks=True,
                show_progress=False,
            )

            if not isinstance(raw_chunks, list):
                raise PdfExtractionError(
                    f"Cannot extract PDF '{source_path}': page-aware Markdown was not returned."
                )

            if len(raw_chunks) != document.page_count:
                raise PdfExtractionError(
                    f"Cannot extract PDF '{source_path}': expected "
                    f"{document.page_count} page chunks, received "
                    f"{len(raw_chunks)}."
                )

            page_sections: list[str] = []

            for index, raw_chunk in enumerate(raw_chunks, start=1):
                if not isinstance(raw_chunk, dict):
                    raise PdfExtractionError(f"Invalid extraction result for source page {index}.")

                metadata = raw_chunk.get("metadata")
                page_number = index

                if isinstance(metadata, dict):
                    reported_page = metadata.get("page_number")
                    if (
                        isinstance(reported_page, int)
                        and not isinstance(reported_page, bool)
                        and reported_page > 0
                    ):
                        page_number = reported_page

                page_text = raw_chunk.get("text", "")
                if not isinstance(page_text, str):
                    raise PdfExtractionError(f"Invalid Markdown text on source page {page_number}.")

                page_text = page_text.strip()

                page_sections.append(f"<!-- source_page: {page_number} -->\n\n{page_text}")

            if not any(section.split("\n\n", 1)[1].strip() for section in page_sections):
                raise PdfExtractionError(
                    f"Cannot extract text from PDF '{source_path}': "
                    "all pages are empty. OCR or another parser may be needed."
                )

            markdown = "\n\n".join(page_sections).rstrip() + "\n"

    except PdfExtractionError:
        raise
    except Exception as exc:
        raise PdfExtractionError(f"Cannot extract PDF '{source_path}': {exc}") from exc

    temporary_path = destination_path.with_name(destination_path.name + ".part")

    try:
        destination_path.parent.mkdir(parents=True, exist_ok=True)

        with temporary_path.open(
            "w",
            encoding="utf-8",
            newline="\n",
        ) as output:
            output.write(markdown)

        temporary_path.replace(destination_path)
        return destination_path

    except OSError as exc:
        raise PdfExtractionError(
            f"Cannot write Markdown output '{destination_path}': {exc}"
        ) from exc
    finally:
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError:
            pass
