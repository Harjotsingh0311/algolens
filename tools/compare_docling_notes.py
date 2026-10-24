from __future__ import annotations

import hashlib
import re
import sys
import time
from pathlib import Path

import torch
import yaml
from docling.datamodel.accelerator_options import (
    AcceleratorDevice,
    AcceleratorOptions,
)
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions, RapidOcrOptions
from docling.document_converter import DocumentConverter, PdfFormatOption

ROOT = Path(__file__).resolve().parents[1]

SOURCE_ID = "L06_TYPED_NOTES"
EXPECTED_SHA256 = "fac37c9721e67c2f5723536ae412bd200ae7580675bd0f53b21f2878af39bc55"

DEFAULT_SOURCE = ROOT / "corpus" / "raw" / "L06_TYPED_NOTES.pdf"
OUTPUT_PATH = ROOT / "corpus" / "experiments" / "pdf_extraction" / "notes_docling_cuda_torch_ocr.md"

# Lines matching likely formulas, notation, or important lecture topics.
CANDIDATE_PATTERN = re.compile(
    r"\\\\(?:frac|log|Theta|Pr|mathbb|sum|sqrt)"
    r"|[≤≥≠∑Σ]"
    r"|AB\s*=\s*C"
    r"|T\s*\("
    r"|quicksort|Frievald|partition|expected time",
    re.IGNORECASE,
)


def stop(message: str) -> None:
    print(f"\nERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def find_manifest_record() -> dict:
    manifest_path = ROOT / "corpus" / "manifest.yaml"

    if not manifest_path.is_file():
        stop(f"Manifest not found: {manifest_path}")

    data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))

    if isinstance(data, dict):
        sources = data.get("sources", [])
    elif isinstance(data, list):
        sources = data
    else:
        stop("Unexpected manifest format. Expected a source list or mapping.")

    if isinstance(sources, dict):
        if SOURCE_ID in sources and isinstance(sources[SOURCE_ID], dict):
            record = dict(sources[SOURCE_ID])
            record.setdefault("id", SOURCE_ID)
            records = [record]
        else:
            records = []
            for key, value in sources.items():
                if isinstance(value, dict):
                    record = dict(value)
                    record.setdefault("id", str(key))
                    records.append(record)
    elif isinstance(sources, list):
        records = sources
    else:
        stop("The manifest 'sources' field must be a list or mapping.")

    record = next(
        (item for item in records if isinstance(item, dict) and item.get("id") == SOURCE_ID),
        None,
    )

    if record is None:
        stop(f"Could not find {SOURCE_ID} in corpus/manifest.yaml.")

    manifest_hash = str(record.get("sha256") or "").strip().lower()

    if manifest_hash != EXPECTED_SHA256:
        stop(
            "The manifest SHA-256 does not match the expected pinned hash. "
            "Review the manifest before extracting."
        )

    return record


def get_source_path(record: dict) -> Path:
    local_path = record.get("local_path") or record.get("local_file") or record.get("local")

    if local_path and "://" not in str(local_path):
        path = Path(str(local_path))
        if not path.is_absolute():
            path = ROOT / path
        return path.resolve()

    return DEFAULT_SOURCE.resolve()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def matching_lines(text: str) -> list[tuple[int, str]]:
    return [
        (number, line.strip())
        for number, line in enumerate(text.splitlines(), start=1)
        if CANDIDATE_PATTERN.search(line)
    ]


def main() -> None:
    print("=" * 72)
    print("AlgoLens: Docling PDF extraction with explicit CUDA")
    print("=" * 72)

    print(f"Python executable : {sys.executable}")
    print(f"PyTorch version   : {torch.__version__}")
    print(f"PyTorch CUDA      : {torch.version.cuda}")
    print(f"CUDA available    : {torch.cuda.is_available()}")

    if not torch.cuda.is_available():
        stop(
            "PyTorch cannot access CUDA in this environment. "
            "Check the project .venv before proceeding."
        )

    gpu_name = torch.cuda.get_device_name(0)
    print(f"GPU               : {gpu_name}")

    # Small operation to confirm this interpreter can execute on CUDA.
    try:
        probe = torch.ones((16, 16), device="cuda")
        _ = probe @ probe
        torch.cuda.synchronize()
        del probe
        torch.cuda.empty_cache()
    except Exception as exc:
        stop(f"A basic CUDA tensor operation failed: {exc}")

    record = find_manifest_record()
    source_path = get_source_path(record)

    if not source_path.is_file():
        stop(f"Typed-notes PDF not found: {source_path}")

    actual_hash = sha256_file(source_path)
    print(f"\nSource PDF        : {source_path}")
    print(f"Expected SHA-256  : {EXPECTED_SHA256}")
    print(f"Actual SHA-256    : {actual_hash}")

    if actual_hash != EXPECTED_SHA256:
        stop("The PDF hash does not match the pinned source. No extraction was performed.")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Explicitly select CUDA instead of leaving device selection on auto.
    pipeline_options = PdfPipelineOptions(
        do_formula_enrichment=True,
        ocr_options=RapidOcrOptions(backend="torch"),
        accelerator_options=AcceleratorOptions(
            device=AcceleratorDevice.CUDA,
        ),
    )

    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(
                pipeline_options=pipeline_options,
            )
        }
    )

    print("\nRequested Docling device: CUDA")
    print("Formula enrichment      : enabled")
    print("Starting conversion. The first run may need to download models...")

    start = time.perf_counter()

    try:
        result = converter.convert(source_path)
        torch.cuda.synchronize()
    except Exception as exc:
        stop(
            "Docling conversion failed. The traceback/error above should "
            f"identify the cause. Details: {type(exc).__name__}: {exc}"
        )

    elapsed = time.perf_counter() - start
    markdown = result.document.export_to_markdown()

    if not isinstance(markdown, str) or not markdown.strip():
        stop("Docling returned empty Markdown. The output was not saved.")

    # Write to a new file, leaving notes.md and notes_docling.md untouched.
    temporary_path = OUTPUT_PATH.with_suffix(".tmp")
    temporary_path.write_text(markdown, encoding="utf-8")
    temporary_path.replace(OUTPUT_PATH)

    print("\n" + "=" * 72)
    print("CUDA extraction completed")
    print("=" * 72)
    print(f"Output file       : {OUTPUT_PATH}")
    print(f"Characters        : {len(markdown):,}")
    print(f"Markdown lines    : {len(markdown.splitlines()):,}")
    print(f"Conversion time   : {elapsed:.2f} seconds")
    print(f"Peak PyTorch GPU memory: {torch.cuda.max_memory_allocated() / (1024**3):.2f} GiB")

    # Compare the available extraction outputs without modifying them.
    comparison_files = [
        ROOT / "corpus" / "experiments" / "pdf_extraction" / "notes.md",
        ROOT / "corpus" / "experiments" / "pdf_extraction" / "notes_docling.md",
        OUTPUT_PATH,
    ]

    print("\nExtraction comparison")
    print("-" * 72)

    for path in comparison_files:
        if not path.is_file():
            print(f"{path.name}: not present; skipped")
            continue

        content = path.read_text(encoding="utf-8")
        candidates = matching_lines(content)

        print(
            f"{path.name}: "
            f"{len(content):,} characters, "
            f"{len(content.splitlines()):,} lines, "
            f"{len(candidates)} candidate formula/topic lines"
        )

    print("\nFormula and topic candidates from the CUDA output")
    print("-" * 72)

    candidates = matching_lines(markdown)

    if not candidates:
        print("No candidate lines matched the review pattern.")
    else:
        for number, line in candidates[:40]:
            print(f"{number:04d}: {line[:260]}")

        if len(candidates) > 40:
            print(f"... {len(candidates) - 40} additional candidate lines omitted.")

    print("\nNext step: manually inspect equations and symbols in the output.")
    print("CUDA was explicitly requested; memory statistics are diagnostic only.")


if __name__ == "__main__":
    main()
