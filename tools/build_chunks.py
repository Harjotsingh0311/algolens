from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from algolens.ingest.chunking import (  # noqa: E402
    build_hierarchical_chunks,
    filter_pdf_quicksort_units,
    filter_transcript_from,
    parse_pdf_markdown,
    parse_transcript_jsonl,
    word_count,
)

SOURCES = [
    {
        "source_id": "L06_TYPED_NOTES",
        "artifact_path": Path("corpus/experiments/pdf_extraction/notes.md"),
        "parser": "pdf",
        "scope_filter": "quicksort_sections",
        "scope_note": (
            "Keep Quicksort, basic Quicksort, pivot selection, randomized "
            "Quicksort, paranoid Quicksort, and related expectations sections."
        ),
        "review_status": "unreviewed_extraction",
    },
    {
        "source_id": "L06_YOUTUBE_CAPTIONS",
        "artifact_path": Path("corpus/processed/transcript.jsonl"),
        "parser": "transcript",
        "scope_filter": "timestamp_lower_bound",
        "time_start_seconds": 2997.340,
        "scope_note": (
            "Start at the Quicksort transition cue at 2997.340 seconds. "
            "Earlier mentions are introductory references rather than the "
            "sustained Quicksort section."
        ),
        "review_status": "pending_spot_check",
    },
]

OUTPUT_DIR = ROOT / "corpus" / "experiments" / "chunking"
PARENTS_PATH = OUTPUT_DIR / "parents.jsonl"
CHILDREN_PATH = OUTPUT_DIR / "children.jsonl"
REPORT_PATH = OUTPUT_DIR / "report.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_manifest() -> dict[str, dict[str, Any]]:
    path = ROOT / "corpus" / "manifest.yaml"
    parsed = yaml.safe_load(path.read_text(encoding="utf-8-sig"))

    sources = parsed.get("sources") if isinstance(parsed, dict) else parsed
    if not isinstance(sources, list):
        raise ValueError("Manifest must contain a list of source records.")

    records: dict[str, dict[str, Any]] = {}
    for record in sources:
        if not isinstance(record, dict) or not record.get("id"):
            raise ValueError("Manifest contains an invalid source record.")

        source_id = str(record["id"])
        if source_id in records:
            raise ValueError(f"Duplicate manifest source ID: {source_id}")

        records[source_id] = record

    return records


def verify_raw_source(source_record: dict[str, Any]) -> str:
    local_path_value = source_record.get("local_path")
    expected_hash = str(source_record.get("sha256") or "").lower()

    if not local_path_value:
        raise ValueError(f"Manifest source {source_record['id']} has no local_path.")
    if len(expected_hash) != 64:
        raise ValueError(f"Manifest source {source_record['id']} has no pinned SHA-256.")

    raw_path = Path(str(local_path_value))
    if not raw_path.is_absolute():
        raw_path = ROOT / raw_path
    raw_path = raw_path.resolve()

    if not raw_path.is_file():
        raise FileNotFoundError(f"Raw source not found: {raw_path}")

    actual_hash = sha256_file(raw_path)
    if actual_hash.lower() != expected_hash:
        raise ValueError(
            f"SHA-256 mismatch for {source_record['id']}: "
            f"expected {expected_hash}, got {actual_hash}"
        )

    return actual_hash


def jsonl_text(records: list[dict[str, Any]]) -> str:
    return "".join(
        json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in records
    )


def verify_parent_child_links(
    parents: list[dict[str, Any]],
    children: list[dict[str, Any]],
) -> None:
    by_parent: dict[str, list[dict[str, Any]]] = {}

    for child in children:
        parent_id = child["parent_id"]
        by_parent.setdefault(parent_id, []).append(child)

    for parent in parents:
        parent_id = parent["chunk_id"]
        linked_children = by_parent.get(parent_id, [])
        linked_children.sort(key=lambda child: child["ordinal"])

        child_ids = [child["chunk_id"] for child in linked_children]
        if child_ids != parent["child_ids"]:
            raise ValueError(f"Invalid child list for parent {parent_id}.")

        reconstructed = "\n".join(child["text"] for child in linked_children)
        if reconstructed != parent["text"]:
            raise ValueError(f"Child text does not reconstruct parent {parent_id}.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build provenance-preserving experimental lecture chunks."
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace existing experimental chunk outputs.",
    )
    args = parser.parse_args()

    output_paths = [PARENTS_PATH, CHILDREN_PATH, REPORT_PATH]
    existing = [path for path in output_paths if path.exists()]
    if existing and not args.overwrite:
        names = "\n".join(str(path.relative_to(ROOT)) for path in existing)
        raise SystemExit(
            f"Chunk outputs already exist. Inspect them or rerun with --overwrite:\n{names}"
        )

    manifest = load_manifest()
    all_parents: list[dict[str, Any]] = []
    all_children: list[dict[str, Any]] = []
    source_reports: list[dict[str, Any]] = []

    for spec in SOURCES:
        source_id = spec["source_id"]
        if source_id not in manifest:
            raise ValueError(f"Missing manifest record for {source_id}.")

        source_record = manifest[source_id]
        raw_sha256 = verify_raw_source(source_record)
        artifact_path = ROOT / spec["artifact_path"]

        if not artifact_path.is_file():
            raise FileNotFoundError(f"Derived source artifact not found: {artifact_path}")

        artifact_sha256 = sha256_file(artifact_path)
        content = artifact_path.read_text(encoding="utf-8-sig")

        if spec["parser"] == "pdf":
            units = filter_pdf_quicksort_units(parse_pdf_markdown(content))
        elif spec["parser"] == "transcript":
            units = parse_transcript_jsonl(content)
            units = filter_transcript_from(
                units,
                start_seconds=float(spec["time_start_seconds"]),
            )
        else:
            raise ValueError(f"Unknown parser: {spec['parser']}")

        parents, children = build_hierarchical_chunks(
            units,
            source_record,
            source_path=artifact_path.relative_to(ROOT).as_posix(),
            artifact_sha256=artifact_sha256,
            review_status=spec["review_status"],
        )

        all_parents.extend(parents)
        all_children.extend(children)

        source_reports.append(
            {
                "source_id": source_id,
                "parser": spec["parser"],
                "source_path": artifact_path.relative_to(ROOT).as_posix(),
                "source_sha256_verified": raw_sha256,
                "artifact_sha256": artifact_sha256,
                "review_status": spec["review_status"],
                "scope_filter": spec["scope_filter"],
                "scope_note": spec["scope_note"],
                "time_start_seconds": spec.get("time_start_seconds"),
                "unit_count": len(units),
                "word_count": sum(word_count(unit.text) for unit in units),
                "parent_count": len(parents),
                "child_count": len(children),
                "parent_word_counts": [parent["word_count"] for parent in parents],
                "child_word_counts": [child["word_count"] for child in children],
            }
        )

    verify_parent_child_links(all_parents, all_children)

    report = {
        "schema_version": 1,
        "status": "experimental_unreviewed_chunks",
        "chunking_parameters": {
            "parent_target_words": 480,
            "parent_min_words": 400,
            "parent_max_words": 600,
            "child_target_words": 160,
            "child_min_words": 120,
            "child_max_words": 200,
        },
        "parent_count": len(all_parents),
        "child_count": len(all_children),
        "sources": source_reports,
        "outputs": {
            "parents": PARENTS_PATH.relative_to(ROOT).as_posix(),
            "children": CHILDREN_PATH.relative_to(ROOT).as_posix(),
        },
        "quality_note": (
            "Chunk sizes are approximate. Small terminal chunks may occur. "
            "The chunker preserves provenance but does not verify extracted "
            "mathematics or caption accuracy."
        ),
    }

    payloads = {
        PARENTS_PATH: jsonl_text(all_parents),
        CHILDREN_PATH: jsonl_text(all_children),
        REPORT_PATH: json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    temporary_paths: list[tuple[Path, Path]] = []
    for target, content in payloads.items():
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_text(content, encoding="utf-8")
        temporary_paths.append((temporary, target))

    for temporary, target in temporary_paths:
        temporary.replace(target)

    print("Chunking completed.")
    print(f"Parents: {len(all_parents)}")
    print(f"Children: {len(all_children)}")
    print(f"Parent JSONL: {PARENTS_PATH}")
    print(f"Child JSONL:  {CHILDREN_PATH}")
    print(f"Report:       {REPORT_PATH}")
    print("Review status is preserved for every source.")


if __name__ == "__main__":
    main()
