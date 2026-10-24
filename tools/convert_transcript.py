"""Verify and convert the pinned Lecture 6 caption file."""

import json
from pathlib import Path

from algolens.ingest.fetch import verify_file_hash
from algolens.ingest.manifest import load_manifest
from algolens.ingest.transcript import convert_vtt_to_jsonl

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ID = "L06_YOUTUBE_CAPTIONS"


def main() -> None:
    manifest_path = ROOT / "corpus" / "manifest.yaml"
    manifest = load_manifest(manifest_path)

    matches = [
        source
        for source in manifest["sources"]
        if source["id"] == SOURCE_ID
    ]

    if len(matches) != 1:
        raise SystemExit(
            f"Expected exactly one manifest record for {SOURCE_ID}."
        )

    record = matches[0]
    expected_hash = record.get("sha256")
    local_path = record.get("local_path")

    if not isinstance(expected_hash, str):
        raise SystemExit(f"{SOURCE_ID} has no pinned SHA-256 hash.")

    if not isinstance(local_path, str) or not local_path.strip():
        raise SystemExit(f"{SOURCE_ID} has no valid local_path.")

    source_path = ROOT / local_path
    destination = ROOT / "corpus" / "processed" / "transcript.jsonl"

    if not source_path.is_file():
        raise SystemExit(f"Caption source does not exist: {source_path}")

    if destination.exists():
        raise SystemExit(
            f"Output already exists: {destination}. "
            "Inspect it before attempting another conversion."
        )

    actual_hash = verify_file_hash(
        source_path,
        expected_hash,
        SOURCE_ID,
    )

    print(f"Verified source: {SOURCE_ID}")
    print(f"SHA-256: {actual_hash}")

    output_path = convert_vtt_to_jsonl(source_path, destination)

    rows = [
        json.loads(line)
        for line in output_path.read_text(encoding="utf-8").splitlines()
    ]

    if not rows:
        raise SystemExit("Conversion produced no transcript records.")

    previous_start = -1.0
    previous_end = 0.0
    largest_gap = 0.0
    word_count = 0

    for number, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            raise SystemExit(f"Record {number} is not a JSON object.")

        if set(row) != {"start", "end", "text"}:
            raise SystemExit(
                f"Record {number} has unexpected fields: {list(row)}"
            )

        start = row["start"]
        end = row["end"]
        text = row["text"]

        if (
            not isinstance(start, (int, float))
            or isinstance(start, bool)
            or not isinstance(end, (int, float))
            or isinstance(end, bool)
        ):
            raise SystemExit(f"Invalid timestamp types in record {number}.")

        if start < 0 or start >= end:
            raise SystemExit(f"Invalid timestamp range in record {number}.")

        if start < previous_start:
            raise SystemExit(f"Timestamps move backwards at record {number}.")

        if not isinstance(text, str) or not text.strip():
            raise SystemExit(f"Empty transcript text in record {number}.")

        if start - previous_end > 30:
            raise SystemExit(
                f"Gap greater than 30 seconds at record {number}."
            )

        if start > previous_end:
            largest_gap = max(largest_gap, start - previous_end)

        previous_start = start
        previous_end = max(previous_end, end)
        word_count += len(text.split())

    print("\n========== TRANSCRIPT SUMMARY ==========")
    print(f"Output: {output_path}")
    print(f"Records: {len(rows)}")
    print(f"Approximate words: {word_count}")
    print(f"First cue: {rows[0]}")
    print(f"Last cue: {rows[-1]}")
    print(f"Largest inter-cue gap: {largest_gap:.3f} seconds")
    print(f"Output size: {output_path.stat().st_size:,} bytes")
    print("JSONL and timestamp validation passed.")


if __name__ == "__main__":
    main()