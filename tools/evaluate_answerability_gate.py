from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import time
from collections import Counter
from pathlib import Path
from typing import Any

from algolens.answerability import AnswerabilityGate
from algolens.evaluation.answerability_metrics import (
    evaluate_answerability_scores,
)
from algolens.retrieval.bm25 import BM25Index, is_answer_eligible
from algolens.retrieval.dense import DEFAULT_MODEL, DenseIndex
from algolens.retrieval.hybrid import HybridIndex
from algolens.retrieval.pipeline import RetrievalPipeline
from algolens.retrieval.rerank import (
    DEFAULT_CROSS_ENCODER_MODEL,
    CrossEncoderReranker,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CHUNKS = ROOT / "corpus/experiments/chunking/children.jsonl"
DEFAULT_QUESTIONS = ROOT / "eval/gold/questions_v0.jsonl"
DEFAULT_OUTPUT = ROOT / "eval/results/answerability_gate_diagnostic.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(f"Input file not found: {path}")

    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in {path}, line {line_number}: {exc}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"{path}, line {line_number}: expected a JSON object.")
        rows.append(row)

    if not rows:
        raise ValueError(f"No records found in {path}.")
    return rows


def nearest_rank(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return ordered[index]


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run diagnostic-only answerability score evaluation on draft labels "
            "and unreviewed Quicksort chunks. Generates no answers."
        )
    )
    parser.add_argument("--chunks", type=Path, default=DEFAULT_CHUNKS)
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--candidate-k", type=int, default=20)
    parser.add_argument("--answer-threshold", type=float, default=1.0)
    parser.add_argument("--partial-threshold", type=float, default=0.0)
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument(
        "--reranker-model",
        default=DEFAULT_CROSS_ENCODER_MODEL,
    )
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    if args.top_k < 1:
        raise SystemExit("--top-k must be at least 1.")
    if args.candidate_k < args.top_k:
        raise SystemExit("--candidate-k must be at least --top-k.")
    if args.answer_threshold <= args.partial_threshold:
        raise SystemExit("--answer-threshold must be greater than --partial-threshold.")
    if not math.isfinite(args.answer_threshold) or not math.isfinite(args.partial_threshold):
        raise SystemExit("Thresholds must be finite.")

    chunk_path = args.chunks if args.chunks.is_absolute() else ROOT / args.chunks
    question_path = args.questions if args.questions.is_absolute() else ROOT / args.questions
    output_path = args.output if args.output.is_absolute() else ROOT / args.output

    if output_path.exists() and not args.overwrite:
        raise SystemExit(
            f"Report already exists: {output_path}. Choose another output or pass --overwrite."
        )

    chunks = load_jsonl(chunk_path)
    questions = load_jsonl(question_path)
    chunk_ids = [str(row.get("chunk_id", "")).strip() for row in chunks]

    if any(not chunk_id for chunk_id in chunk_ids):
        raise SystemExit("Every corpus chunk must have a nonempty chunk_id.")
    if len(set(chunk_ids)) != len(chunk_ids):
        raise SystemExit("Duplicate chunk IDs detected in the diagnostic corpus.")

    # This runner intentionally refuses approved evidence; it is only for
    # the current experimental corpus and draft-label exploration.
    eligible_input_ids = [row["chunk_id"] for row in chunks if is_answer_eligible(row)]
    if eligible_input_ids:
        raise SystemExit(
            "This diagnostic runner expects an all-ineligible experimental corpus. "
            f"Found eligible chunks: {eligible_input_ids[:10]}"
        )

    if len(questions) != 30:
        raise SystemExit(f"Expected the current 30-question draft set, found {len(questions)}.")

    seen_question_ids: set[str] = set()
    for row in questions:
        question_id = str(row.get("question_id", "")).strip()
        if not question_id or question_id in seen_question_ids:
            raise SystemExit(f"Missing or duplicate question ID: {question_id!r}")
        seen_question_ids.add(question_id)

        if not isinstance(row.get("question"), str) or not row["question"].strip():
            raise SystemExit(f"{question_id}: empty or invalid question.")
        if not isinstance(row.get("answerable"), bool):
            raise SystemExit(f"{question_id}: answerable label must be boolean.")
        if row.get("label_status") != "draft_needs_human_review":
            raise SystemExit(
                f"{question_id}: expected draft_needs_human_review; "
                "this runner is not the approved-label evaluation."
            )

        gold_ids = row.get("gold_passage_ids")
        if not isinstance(gold_ids, list):
            raise SystemExit(f"{question_id}: gold_passage_ids must be a list.")
        if row["answerable"] and not gold_ids:
            raise SystemExit(f"{question_id}: answerable question has no gold IDs.")
        if not row["answerable"] and gold_ids:
            raise SystemExit(f"{question_id}: unanswerable question has gold IDs.")
        if not set(gold_ids).issubset(set(chunk_ids)):
            raise SystemExit(f"{question_id}: gold passage IDs are absent from corpus.")

    label_counts = Counter(str(row["answerable"]) for row in questions)
    label_status_counts = Counter(str(row["label_status"]) for row in questions)

    device = None if args.device == "auto" else args.device
    print(f"Diagnostic chunks: {len(chunks)}")
    print(f"Draft questions: {len(questions)}")
    print(f"Answerability labels: {dict(label_counts)}")
    print(f"Label statuses: {dict(label_status_counts)}")
    print(f"Dense model: {args.model}")
    print(f"Cross-encoder: {args.reranker_model}")
    print(f"Requested device: {args.device}")
    print("Mode: diagnostic-only; answer generation disabled")

    bm25_start = time.perf_counter()
    bm25 = BM25Index(chunks, include_unreviewed=True)
    bm25_seconds = time.perf_counter() - bm25_start

    dense_start = time.perf_counter()
    dense = DenseIndex(
        chunks,
        include_unreviewed=True,
        model_name=args.model,
        device=device,
    )
    dense_seconds = time.perf_counter() - dense_start

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

    gate = AnswerabilityGate()
    details: list[dict[str, Any]] = []
    labels: list[bool] = []
    top_scores: list[float | None] = []
    latencies: list[float] = []

    for index, question_row in enumerate(questions, start=1):
        question_id = question_row["question_id"]
        query = question_row["question"]

        start = time.perf_counter()
        results = pipeline.search(query, top_k=args.top_k)
        elapsed = time.perf_counter() - start
        latencies.append(elapsed)

        # This is the actual production policy assessment. Since all retrieved
        # chunks are unapproved, it should abstain even if their ranking score
        # is numerically high.
        actual_assessment = gate.assess(results)
        if actual_assessment.decision != "abstain":
            raise SystemExit(f"{question_id}: unapproved evidence escaped the gate.")
        if actual_assessment.reason != "no_eligible_evidence":
            raise SystemExit(
                f"{question_id}: unexpected production gate reason {actual_assessment.reason!r}."
            )

        for result in results:
            if result.get("eligible_for_answer") is not False:
                raise SystemExit(f"{question_id}: experimental result became answer-eligible.")
            if is_answer_eligible(result):
                raise SystemExit(f"{question_id}: review gate accepted an experimental result.")

        top_score: float | None = None
        if results:
            raw_score = results[0].get("rerank_score")
            if (
                isinstance(raw_score, bool)
                or not isinstance(raw_score, (int, float))
                or not math.isfinite(float(raw_score))
            ):
                raise SystemExit(f"{question_id}: invalid top reranker score.")
            top_score = float(raw_score)

        labels.append(question_row["answerable"])
        top_scores.append(top_score)

        gold_ids = set(question_row["gold_passage_ids"])
        ranked_ids = [str(result["chunk_id"]) for result in results]
        top_results = [
            {
                "rank": rank,
                "chunk_id": result["chunk_id"],
                "citation": result.get("citation"),
                "review_status": result.get("review_status"),
                "rerank_score": result.get("rerank_score"),
                "eligible_for_answer": False,
                "matches_gold_id": result["chunk_id"] in gold_ids,
            }
            for rank, result in enumerate(results, start=1)
        ]

        details.append(
            {
                "question_id": question_id,
                "question": query,
                "question_type": question_row.get("question_type"),
                "difficulty": question_row.get("difficulty"),
                "draft_answerable_label": question_row["answerable"],
                "label_status": question_row["label_status"],
                "gold_passage_ids": question_row["gold_passage_ids"],
                "diagnostic_top_rerank_score": top_score,
                "exploratory_score_based_prediction": None,
                "production_gate_decision": actual_assessment.decision,
                "production_gate_reason": actual_assessment.reason,
                "production_gate_thresholds_calibrated": (actual_assessment.thresholds_calibrated),
                "retrieval_latency_seconds": elapsed,
                "top_results": top_results,
                "gold_passage_hit_at_k": any(chunk_id in gold_ids for chunk_id in ranked_ids),
            }
        )

        print(
            f"[{index:02d}/{len(questions)}] {question_id} | "
            f"results={len(results)} | "
            f"top_score={top_score} | "
            f"production_gate=abstain (unreviewed evidence)"
        )

    metric_report = evaluate_answerability_scores(
        answerable=labels,
        top_scores=top_scores,
        answer_threshold=args.answer_threshold,
        partial_threshold=args.partial_threshold,
    )
    for index, prediction in enumerate(metric_report["predictions"]):
        details[index]["exploratory_score_based_prediction"] = prediction

    query_stats = {
        "query_count": len(latencies),
        "p50_seconds": nearest_rank(latencies, 0.50),
        "p95_seconds": nearest_rank(latencies, 0.95),
        "mean_seconds": statistics.fmean(latencies) if latencies else None,
        "bm25_build_seconds": bm25_seconds,
        "dense_build_seconds_including_model_and_embeddings": dense_seconds,
    }

    report = {
        "schema_version": 1,
        "status": "exploratory_answerability_gate_score_diagnostic",
        "diagnostic_only": True,
        "answer_generation_permitted": False,
        "retrieval_eligible": False,
        "labels_reviewed": False,
        "label_status_counts": dict(label_status_counts),
        "split_available": False,
        "thresholds_calibrated": False,
        "requested_device": args.device,
        "resolved_dense_device": str(getattr(dense, "device", "unknown")),
        "resolved_cross_encoder_device": str(getattr(reranker.encoder, "device", "unknown")),
        "dense_model": args.model,
        "cross_encoder_model": args.reranker_model,
        "corpus_path": chunk_path.relative_to(ROOT).as_posix()
        if chunk_path.is_relative_to(ROOT)
        else str(chunk_path),
        "corpus_sha256": sha256_file(chunk_path),
        "question_path": question_path.relative_to(ROOT).as_posix()
        if question_path.is_relative_to(ROOT)
        else str(question_path),
        "question_sha256": sha256_file(question_path),
        "chunk_count": len(chunks),
        "all_input_chunks_ineligible": True,
        "question_count": len(questions),
        "draft_answerable_count": sum(labels),
        "draft_unanswerable_count": len(labels) - sum(labels),
        "top_k": args.top_k,
        "candidate_k": args.candidate_k,
        "exploratory_score_thresholds": {
            "answer_threshold": args.answer_threshold,
            "partial_threshold": args.partial_threshold,
            "meaning": (
                "Provisional score cutoffs for diagnostic analysis only; "
                "not calibrated probabilities and not frozen."
            ),
        },
        "diagnostic_metrics": metric_report,
        "timings": query_stats,
        "production_gate_behavior": {
            "decision": "abstain",
            "reason": "no_eligible_evidence",
            "explanation": (
                "The current corpus contains only unreviewed experimental chunks. "
                "The production gate therefore refuses to treat these results as evidence."
            ),
        },
        "questions": details,
        "limitations": [
            "All labels are draft_needs_human_review and have not been independently validated.",
            "The question set has no defined dev/test split.",
            (
                "Score-threshold predictions are exploratory diagnostics, "
                "not actual production decisions."
            ),
            (
                "Actual production gate decisions abstain because every "
                "retrieved passage is unapproved."
            ),
            "Cross-encoder scores are ranking scores, not probabilities.",
            "No answers were generated or evaluated.",
            (
                "Do not use these results to claim a calibrated threshold "
                "or answer-quality improvement."
            ),
        ],
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists() and not args.overwrite:
        raise SystemExit(
            f"Output already exists: {output_path}. "
            "Use --overwrite after reviewing the existing report."
        )

    temp_path = output_path.with_name(output_path.name + ".tmp")
    if temp_path.exists():
        raise SystemExit(f"Temporary output already exists: {temp_path}")

    temp_path.write_text(
        json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temp_path.replace(output_path)

    print("\nDIAGNOSTIC EVALUATION COMPLETED")
    print("Coverage:", metric_report["coverage"])
    print("Risk among accepted questions:", metric_report["risk"])
    print("AURC:", metric_report["aurc"])
    print("Thresholds calibrated:", report["thresholds_calibrated"])
    print(
        "All production gate decisions abstained:",
        all(item["production_gate_decision"] == "abstain" for item in details),
    )
    print("Report:", output_path)


if __name__ == "__main__":
    main()
