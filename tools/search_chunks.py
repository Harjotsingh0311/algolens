from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from algolens.retrieval.bm25 import BM25Index  # noqa: E402

CHILDREN_PATH = ROOT / "corpus" / "experiments" / "chunking" / "children.jsonl"


def load_chunks(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(f"Chunk corpus not found: {path}")

    chunks: list[dict[str, Any]] = []

    for line_number, line in enumerate(
        path.read_text(encoding="utf-8-sig").splitlines(),
        start=1,
    ):
        if not line.strip():
            continue

        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON on line {line_number}: {exc}") from exc

        if not isinstance(row, dict):
            raise ValueError(f"Line {line_number} must be a JSON object.")

        chunks.append(row)

    return chunks


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Search the experimental AlgoLens child-chunk corpus."
    )
    parser.add_argument("query", nargs="+", help="Search query.")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument(
        "--include-unreviewed",
        action="store_true",
        help=("Diagnostic only: include chunks that are not approved as answer evidence."),
    )
    args = parser.parse_args()

    chunks = load_chunks(CHILDREN_PATH)
    index = BM25Index(
        chunks,
        include_unreviewed=args.include_unreviewed,
    )

    query = " ".join(args.query)
    results = index.search(query, top_k=args.top_k)

    print(f"Query: {query}")
    print(f"Index documents: {index.document_count}")
    print(f"Results: {len(results)}")

    if not results and not args.include_unreviewed:
        print(
            "No approved chunks are indexed. Current corpus chunks are "
            "unreviewed or pending review. For diagnostic search only, "
            "rerun with --include-unreviewed."
        )
        return

    for rank, result in enumerate(results, start=1):
        citation = result.get("citation", {})

        preview = str(result.get("text", "")).replace("\n", " ")
        if len(preview) > 500:
            preview = preview[:497] + "..."

        output = {
            "rank": rank,
            "score": round(float(result["score"]), 6),
            "chunk_id": result["chunk_id"],
            "parent_id": result.get("parent_id"),
            "source_id": result.get("source_id"),
            "review_status": result.get("review_status"),
            "eligible_for_answer": result["eligible_for_answer"],
            "citation": citation,
            "preview": preview,
        }

        print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
