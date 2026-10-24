"""Verify and extract the actual typed lecture notes PDF."""

import re
from pathlib import Path

import pymupdf

from algolens.ingest.fetch import verify_file_hash
from algolens.ingest.manifest import load_manifest
from algolens.ingest.pdf import extract_pdf_to_markdown

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ID = "L06_TYPED_NOTES"


def main() -> None:
    manifest = load_manifest(ROOT / "corpus" / "manifest.yaml")
    sources = [s for s in manifest["sources"] if s["id"] == SOURCE_ID]

    if len(sources) != 1:
        raise SystemExit(f"Expected exactly one source: {SOURCE_ID}")

    record = sources[0]
    expected_hash = record.get("sha256")
    local_path = record.get("local_path")

    if not isinstance(expected_hash, str):
        raise SystemExit("Typed-notes SHA-256 is not pinned.")

    if not isinstance(local_path, str):
        raise SystemExit("Typed-notes local_path is missing.")

    pdf_path = ROOT / local_path
    output_path = ROOT / "corpus" / "experiments" / "pdf_extraction" / "notes.md"

    if not pdf_path.is_file():
        raise SystemExit(f"PDF not found: {pdf_path}")

    if output_path.exists():
        raise SystemExit(f"Output already exists: {output_path}. Inspect it first.")

    actual_hash = verify_file_hash(pdf_path, expected_hash, SOURCE_ID)
    print(f"Verified PDF SHA-256: {actual_hash}")

    with pymupdf.open(pdf_path) as document:
        page_count = document.page_count
        native_text_lengths = [len(page.get_text().strip()) for page in document]

    print(f"PDF page count: {page_count}")
    print(f"Native extracted characters per page: {native_text_lengths}")

    extract_pdf_to_markdown(pdf_path, output_path)

    markdown = output_path.read_text(encoding="utf-8")

    page_markers = re.findall(
        r"(?m)^<!-- source_page:\s*(\d+)\s*-->$",
        markdown,
    )
    headings = re.findall(r"(?m)^#{1,6}\s+.+$", markdown)
    formula_lines = [
        line.strip()
        for line in markdown.splitlines()
        if line.strip()
        and re.search(
            r"(?:=|∑|Σ|Θ|Ω|O\(|E\[|\\log|\\mathbb|\\frac)",
            line,
        )
    ]

    print("\n========== EXTRACTION REPORT ==========")
    print(f"Markdown output: {output_path}")
    print(f"Output size: {output_path.stat().st_size:,} bytes")
    print(f"Page markers: {len(page_markers)}")
    print(f"Unique page markers: {len(set(page_markers))}")
    print(f"Headings found: {len(headings)}")

    print("\n========== HEADINGS ==========")
    for heading in headings[:30]:
        print(heading)

    print("\n========== FORMULA CANDIDATES ==========")
    for line in formula_lines[:20]:
        print(line[:250])

    print("\n========== EXTRACTED TEXT PREVIEW ==========")
    print(markdown[:2500])

    if len(page_markers) != page_count:
        print("\nREVIEW REQUIRED: page marker count differs from PDF page count.")
    elif not markdown.strip():
        print("\nREVIEW REQUIRED: extracted Markdown is empty.")
    else:
        print("\nPage-aware extraction completed. Formula review is still required.")


if __name__ == "__main__":
    main()
