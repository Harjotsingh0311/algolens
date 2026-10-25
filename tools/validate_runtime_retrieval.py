from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from algolens.retrieval.bm25 import BM25Index, is_answer_eligible  # noqa: E402
from algolens.retrieval.dense import DEFAULT_MODEL, DenseIndex  # noqa: E402
from algolens.retrieval.hybrid import HybridIndex  # noqa: E402
from algolens.retrieval.pipeline import RetrievalPipeline  # noqa: E402
from algolens.retrieval.rerank import (  # noqa: E402
    DEFAULT_CROSS_ENCODER_MODEL,
    CrossEncoderReranker,
)

DEFAULT_CHUNKS = ROOT / "corpus/experiments/chunking/children.jsonl"
DEFAULT_OUTPUT = ROOT / "eval/results/runtime_retrieval_smoke.json"
DEFAULT_QUERY = (
    "How does randomized Quicksort achieve expected Theta(n log n) "
    "running time, and what recurrence explains the bound?"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_chunks(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(f"Chunk corpus not found: {path}")

    chunks: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue

        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in {path}, line {line_number}: {exc}") from exc

        if not isinstance(record, dict):
            raise ValueError(f"Chunk line {line_number} must be a JSON object.")

        chunk_id = str(record.get("chunk_id", "")).strip()
        if not chunk_id:
            raise ValueError(f"Chunk line {line_number} has no chunk_id.")
        if chunk_id in seen_ids:
            raise ValueError(f"Duplicate chunk ID: {chunk_id}")
        if not isinstance(record.get("text"), str) or not record["text"].strip():
            raise ValueError(f"Chunk {chunk_id} has missing or empty text.")
        if not isinstance(record.get("citation"), dict):
            raise ValueError(f"Chunk {chunk_id} has no structured citation.")

        seen_ids.add(chunk_id)
        chunks.append(record)

    if not chunks:
        raise ValueError(f"No usable chunks found in {path}.")

    return chunks


def validate_results(
    results: list[dict[str, Any]],
    source_chunks: list[dict[str, Any]],
) -> None:
    source_by_id = {str(chunk["chunk_id"]): chunk for chunk in source_chunks}
    result_ids: set[str] = set()

    for result in results:
        chunk_id = str(result.get("chunk_id", ""))

        if chunk_id not in source_by_id:
            raise ValueError(f"Pipeline returned an unknown chunk ID: {chunk_id}")
        if chunk_id in result_ids:
            raise ValueError(f"Pipeline returned duplicate chunk ID: {chunk_id}")
        result_ids.add(chunk_id)

        original = source_by_id[chunk_id]
        if result.get("citation") != original.get("citation"):
            raise ValueError(f"Citation changed for chunk {chunk_id}.")
        if result.get("source_id") != original.get("source_id"):
            raise ValueError(f"Source ID changed for chunk {chunk_id}.")
        if result.get("review_status") != original.get("review_status"):
            raise ValueError(f"Review status changed for chunk {chunk_id}.")

        if is_answer_eligible(result):
            raise ValueError(f"Diagnostic result incorrectly became answer-eligible: {chunk_id}")
        if result.get("eligible_for_answer") is not False:
            raise ValueError(f"Diagnostic result has an unsafe eligibility field: {chunk_id}")

        if result.get("retrieval_method") != "hybrid_rff":
            raise ValueError(f"Missing hybrid retrieval metadata for {chunk_id}.")
        if result.get("reranking_method") != "cross_encoder":
            raise ValueError(f"Missing cross-encoder metadata for {chunk_id}.")

        for field in ("score", "rerank_score"):
            value = result.get(field)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
            ):
                raise ValueError(f"Invalid {field} for chunk {chunk_id}.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run a diagnostic-only runtime retrieval smoke test over experimental "
            "child chunks. Does not generate answers."
        )
    )
    parser.add_argument("--query", default=DEFAULT_QUERY)
    parser.add_argument("--chunks", type=Path, default=DEFAULT_CHUNKS)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--candidate-k", type=int, default=20)
    parser.add_argument(
        "--device",
        choices=["auto", "cpu", "cuda"],
        default="auto",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument(
        "--reranker-model",
        default=DEFAULT_CROSS_ENCODER_MODEL,
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace the output report if it already exists.",
    )
    args = parser.parse_args()

    if not args.query.strip():
        raise SystemExit("--query cannot be empty.")
    if args.top_k < 1:
        raise SystemExit("--top-k must be at least 1.")
    if args.candidate_k < args.top_k:
        raise SystemExit("--candidate-k must be at least --top-k.")

    chunk_path = args.chunks if args.chunks.is_absolute() else ROOT / args.chunks
    output_path = args.output if args.output.is_absolute() else ROOT / args.output

    if output_path.exists() and not args.overwrite:
        raise SystemExit(
            f"Output already exists: {output_path}. "
            "Choose another --output path or pass --overwrite."
        )

    chunks = load_chunks(chunk_path)
    corpus_sha256 = sha256_file(chunk_path)

    # This smoke test is deliberately scoped to experimental, unapproved data.
    # Stop if its status changes instead of accidentally testing answer-eligible data.
    eligible_input_ids = [str(chunk["chunk_id"]) for chunk in chunks if is_answer_eligible(chunk)]
    if eligible_input_ids:
        raise SystemExit(
            "Expected an all-ineligible diagnostic corpus, but found answer-eligible "
            f"chunks: {eligible_input_ids[:10]}"
        )

    device = None if args.device == "auto" else args.device

    print(f"Experimental child corpus: {chunk_path}")
    print(f"Chunk count: {len(chunks)}")
    print(f"Chunk-file SHA-256: {corpus_sha256}")
    print(f"Dense model: {args.model}")
    print(f"Cross-encoder: {args.reranker_model}")
    print(f"Requested device: {args.device}")
    print("Mode: diagnostic-only; answer generation disabled")

    bm25_start = time.perf_counter()
    bm25 = BM25Index(chunks, include_unreviewed=True)
    bm25_build_seconds = time.perf_counter() - bm25_start

    dense_start = time.perf_counter()
    dense = DenseIndex(
        chunks,
        include_unreviewed=True,
        model_name=args.model,
        device=device,
    )
    dense_build_seconds = time.perf_counter() - dense_start

    hybrid = HybridIndex(
        chunks,
        bm25_index=bm25,
        dense_index=dense,
        include_unreviewed=True,
    )
    reranker = CrossEncoderReranker(
        model_name=args.reranker_model,
        device=device,
        include_unreviewed=True,
    )
    pipeline = RetrievalPipeline(
        hybrid_index=hybrid,
        reranker=reranker,
        candidate_k=args.candidate_k,
        include_unreviewed=True,
    )

    cold_start = time.perf_counter()
    cold_results = pipeline.search(args.query, top_k=args.top_k)
    cold_seconds = time.perf_counter() - cold_start
    validate_results(cold_results, chunks)

    # Second call reuses the loaded dense encoder and cross-encoder.
    warm_start = time.perf_counter()
    warm_results = pipeline.search(args.query, top_k=args.top_k)
    warm_seconds = time.perf_counter() - warm_start
    validate_results(warm_results, chunks)

    report: dict[str, Any] = {
        "schema_version": 1,
        "status": "diagnostic_runtime_retrieval_smoke_test",
        "diagnostic_only": True,
        "answer_generation_permitted": False,
        "retrieval_eligible": False,
        "query": args.query,
        "corpus_path": chunk_path.relative_to(ROOT).as_posix()
        if chunk_path.is_relative_to(ROOT)
        else str(chunk_path),
        "corpus_sha256": corpus_sha256,
        "chunk_count": len(chunks),
        "all_input_chunks_ineligible": True,
        "dense_model": args.model,
        "cross_encoder_model": args.reranker_model,
        "requested_device": args.device,
        "resolved_dense_device": str(dense.device),
        "resolved_cross_encoder_device": str(getattr(reranker.encoder, "device", "unknown")),
        "top_k": args.top_k,
        "candidate_k": args.candidate_k,
        "timings_seconds": {
            "bm25_index_build": bm25_build_seconds,
            "dense_index_build_including_model_and_embeddings": dense_build_seconds,
            "first_query_including_lazy_cross_encoder_load": cold_seconds,
            "second_warm_query": warm_seconds,
        },
        "results": [
            {
                "rank": rank,
                "chunk_id": result["chunk_id"],
                "citation": result["citation"],
                "review_status": result.get("review_status"),
                "hybrid_rrf_score": result["score"],
                "cross_encoder_rerank_score": result["rerank_score"],
                "eligible_for_answer": False,
            }
            for rank, result in enumerate(warm_results, start=1)
        ],
        "checks": {
            "hybrid_retrieval_executed": True,
            "cross_encoder_executed": True,
            "citation_preservation": "passed",
            "source_metadata_preservation": "passed",
            "finite_scores": "passed",
            "answer_eligibility_gate": "passed",
            "answer_generation": "not_run",
        },
        "limitations": [
            "Single diagnostic query; not a benchmark.",
            "Experimental source chunks are unreviewed.",
            "No answer was generated or evaluated.",
            "Scores are ranking scores, not probabilities.",
            "Cold and warm timing cover different initialization costs.",
        ],
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output_path.with_name(output_path.name + ".tmp")
    if temp_path.exists():
        raise SystemExit(f"Temporary output already exists: {temp_path}")

    temp_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temp_path.replace(output_path)

    print("\nSmoke test PASSED.")
    print("Cold query seconds:", round(cold_seconds, 3))
    print("Warm query seconds:", round(warm_seconds, 3))
    print("Results:", len(warm_results))
    for row in report["results"]:
        print(
            f"  {row['rank']}. {row['chunk_id']} | "
            f"{row['citation'].get('display', '?')} | "
            f"RRF={row['hybrid_rrf_score']:.6f} | "
            f"rerank={row['cross_encoder_rerank_score']:.4f} | "
            f"eligible={row['eligible_for_answer']}"
        )
    print("Answer generation permitted: False")
    print("Report:", output_path)


if __name__ == "__main__":
    main()
