from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from algolens.retrieval.dense import (  # noqa: E402
    DEFAULT_MODEL,
    DenseIndex,
)

CHILDREN_PATH = ROOT / "corpus" / "experiments" / "chunking" / "children.jsonl"


def load_chunks(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(f"Chunk corpus not found: {path}")

    rows: list[dict[str, Any]] = []
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

        rows.append(row)

    return rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Search the experimental AlgoLens corpus using embeddings."
    )
    parser.add_argument("query", nargs="+", help="Search query.")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument(
        "--device",
        choices=["auto", "cpu", "cuda"],
        default="auto",
    )
    parser.add_argument(
        "--include-unreviewed",
        action="store_true",
        help="Diagnostic only; returned chunks remain ineligible for answers.",
    )
    args = parser.parse_args()

    device: str | None = None if args.device == "auto" else args.device

    if device == "cuda":
        import torch

        if not torch.cuda.is_available():
            raise SystemExit("CUDA was requested but PyTorch reports it unavailable.")

    chunks = load_chunks(CHILDREN_PATH)
    index = DenseIndex(
        chunks,
        include_unreviewed=args.include_unreviewed,
        model_name=args.model,
        device=device,
    )

    query = " ".join(args.query)
    results = index.search(query, top_k=args.top_k)

    print(f"Query: {query}")
    print(f"Model: {args.model}")
    print(f"Device: {index.device}")
    print(f"Indexed documents: {len(index.chunks)}")
    print(f"Results: {len(results)}")

    if not results:
        if not args.include_unreviewed:
            print(
                "No approved chunks are indexed. Use --include-unreviewed "
                "for diagnostic retrieval only."
            )
        return

    for rank, result in enumerate(results, start=1):
        preview = str(result.get("text", "")).replace("\n", " ")
        if len(preview) > 500:
            preview = preview[:497] + "..."

        print(
            json.dumps(
                {
                    "rank": rank,
                    "score": round(float(result["score"]), 6),
                    "chunk_id": result["chunk_id"],
                    "parent_id": result.get("parent_id"),
                    "source_id": result.get("source_id"),
                    "review_status": result.get("review_status"),
                    "eligible_for_answer": result["eligible_for_answer"],
                    "citation": result.get("citation"),
                    "preview": preview,
                },
                ensure_ascii=False,
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
