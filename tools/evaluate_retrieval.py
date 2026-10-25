from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from algolens.evaluation.retrieval_metrics import (  # noqa: E402
    evaluate_rankings,
)
from algolens.retrieval.bm25 import (  # noqa: E402
    BM25Index,
    reciprocal_rank_fusion,
)
from algolens.retrieval.dense import (  # noqa: E402
    DEFAULT_MODEL,
    DenseIndex,
)

CHILDREN_PATH = ROOT / "corpus" / "experiments" / "chunking" / "children.jsonl"
QUESTIONS_PATH = ROOT / "eval" / "gold" / "questions_v0.jsonl"
DEFAULT_OUTPUT_DIR = ROOT / "eval" / "results"
APPROVED_LABEL_STATUSES = {"reviewed", "human_verified"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(f"Required file not found: {path}")

    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8-sig").splitlines(),
        start=1,
    ):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in {path} line {line_number}: {exc}") from exc
        if not isinstance(record, dict):
            raise ValueError(f"{path} line {line_number} must be a JSON object.")
        records.append(record)
    return records


def validate_questions(
    questions: list[dict[str, Any]],
    chunks: list[dict[str, Any]],
    *,
    allow_draft_labels: bool,
) -> None:
    if len(questions) != 30:
        raise ValueError(f"Expected exactly 30 questions in v0; found {len(questions)}.")

    chunk_ids = [str(row.get("chunk_id", "")) for row in chunks]
    if not all(chunk_ids) or len(chunk_ids) != len(set(chunk_ids)):
        raise ValueError("Child corpus has missing or duplicate chunk IDs.")
    known_ids = set(chunk_ids)

    question_ids = [str(row.get("question_id", "")) for row in questions]
    if not all(question_ids) or len(question_ids) != len(set(question_ids)):
        raise ValueError("Gold set has missing or duplicate question IDs.")

    drafts = []
    for question in questions:
        required = {
            "question_id",
            "question",
            "question_type",
            "difficulty",
            "answerable",
            "gold_passage_ids",
            "key_points",
            "label_status",
        }
        missing = required - set(question)
        if missing:
            raise ValueError(
                f"{question.get('question_id', '?')} missing fields: {sorted(missing)}"
            )

        if question["answerable"] is True and not question["gold_passage_ids"]:
            raise ValueError(
                f"{question['question_id']} is answerable but has no gold passage IDs."
            )
        if question["answerable"] is False and question["gold_passage_ids"]:
            raise ValueError(f"{question['question_id']} is unanswerable but has gold passage IDs.")

        unknown = set(question["gold_passage_ids"]) - known_ids
        if unknown:
            raise ValueError(
                f"{question['question_id']} references unknown passage IDs: {sorted(unknown)}"
            )

        status = str(question["label_status"]).strip().casefold()
        if status not in APPROVED_LABEL_STATUSES:
            drafts.append(str(question["question_id"]))

    if drafts and not allow_draft_labels:
        raise ValueError(
            "Gold labels are not all human-verified. Review the question set "
            "or pass --allow-draft-labels for a provisional diagnostic run. "
            f"Draft question count: {len(drafts)}."
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate BM25, dense, or hybrid-RRF passage retrieval."
    )
    parser.add_argument(
        "--retriever",
        choices=["bm25", "dense", "hybrid-rff"],
        required=True,
    )
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--candidate-k", type=int, default=10)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    parser.add_argument(
        "--allow-draft-labels",
        action="store_true",
        help="Allow provisional evaluation; report will remain marked draft.",
    )
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Permit replacing an existing report at the selected output path.",
    )
    args = parser.parse_args()

    if args.top_k < 1 or args.candidate_k < 1:
        raise SystemExit("--top-k and --candidate-k must be positive integers.")

    questions = load_jsonl(QUESTIONS_PATH)
    chunks = load_jsonl(CHILDREN_PATH)
    validate_questions(
        questions,
        chunks,
        allow_draft_labels=args.allow_draft_labels,
    )

    output_path = args.output
    if output_path is None:
        suffix = "draft" if args.allow_draft_labels else "reviewed"
        output_path = DEFAULT_OUTPUT_DIR / f"{args.retriever}_{suffix}.json"
    elif not output_path.is_absolute():
        output_path = ROOT / output_path

    if output_path.exists() and not args.overwrite:
        raise SystemExit(
            f"Output already exists: {output_path}. Choose another --output "
            "or pass --overwrite after inspecting it."
        )

    evaluation_depth = max(args.top_k, 10)
    candidate_depth = max(args.candidate_k, evaluation_depth)

    bm25 = None
    dense = None

    if args.retriever in {"bm25", "hybrid-rff"}:
        bm25 = BM25Index(chunks, include_unreviewed=True)

    if args.retriever in {"dense", "hybrid-rff"}:
        chosen_device = None if args.device == "auto" else args.device
        dense = DenseIndex(
            chunks,
            include_unreviewed=True,
            model_name=args.model,
            device=chosen_device,
        )

    rankings: dict[str, list[str]] = {}
    query_traces: list[dict[str, Any]] = []

    for question in questions:
        question_id = str(question["question_id"])
        query = str(question["question"]).strip()

        if args.retriever == "bm25":
            assert bm25 is not None
            found = bm25.search(query, top_k=evaluation_depth)
            ranked_ids = [str(row["chunk_id"]) for row in found]
            component_trace: dict[str, Any] = {"bm25": ranked_ids}
        elif args.retriever == "dense":
            assert dense is not None
            found = dense.search(query, top_k=evaluation_depth)
            ranked_ids = [str(row["chunk_id"]) for row in found]
            component_trace = {"dense": ranked_ids}
        else:
            assert bm25 is not None and dense is not None
            bm25_found = bm25.search(query, top_k=candidate_depth)
            dense_found = dense.search(query, top_k=candidate_depth)
            bm25_ids = [str(row["chunk_id"]) for row in bm25_found]
            dense_ids = [str(row["chunk_id"]) for row in dense_found]
            fused = reciprocal_rank_fusion(
                [bm25_ids, dense_ids],
                k=60,
                limit=evaluation_depth,
            )
            ranked_ids = [str(row["chunk_id"]) for row in fused]
            component_trace = {
                "bm25": bm25_ids,
                "dense": dense_ids,
                "hybrid_rff": ranked_ids,
            }

        rankings[question_id] = ranked_ids
        query_traces.append(
            {
                "question_id": question_id,
                "answerable": bool(question["answerable"]),
                "ranked_passage_ids": ranked_ids,
                "component_rankings": component_trace,
            }
        )

    results = evaluate_rankings(questions, rankings)
    draft_count = sum(
        str(row["label_status"]).casefold() not in APPROVED_LABEL_STATUSES for row in questions
    )
    dense_device = dense.device if dense is not None else None

    report = {
        "report_version": 1,
        "evaluation_status": (
            "provisional_draft_labels" if draft_count else "human_reviewed_labels"
        ),
        "diagnostic_only": True,
        "answer_generation_permitted": False,
        "retriever": args.retriever,
        "model": args.model if dense is not None else None,
        "dense_device": dense_device,
        "question_set_path": QUESTIONS_PATH.relative_to(ROOT).as_posix(),
        "question_set_sha256": sha256_file(QUESTIONS_PATH),
        "corpus_path": CHILDREN_PATH.relative_to(ROOT).as_posix(),
        "corpus_sha256": sha256_file(CHILDREN_PATH),
        "label_status_counts": {
            "draft_needs_human_review": draft_count,
            "reviewed_or_human_verified": len(questions) - draft_count,
        },
        "retrieval_depth": evaluation_depth,
        "candidate_depth": candidate_depth,
        **results,
        "query_traces": query_traces,
        "limitations": [
            "Gold labels are draft until every question is human-reviewed.",
            "The corpus contains unreviewed extracted notes and pending-review captions.",
            "Unanswerable questions are not used to calculate retrieval Recall, MRR, or nDCG.",
            "This is a retrieval evaluation, not an answer-quality or abstention evaluation.",
        ],
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    temp_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temp_path.replace(output_path)

    print(f"Evaluation status: {report['evaluation_status']}")
    print(f"Retriever: {args.retriever}")
    print(f"Questions: {len(questions)}")
    print(f"Answerable scored: {results['answerable_question_count']}")
    print(f"Unanswerable excluded from retrieval metrics: {results['unanswerable_question_count']}")
    print("Retrieval metrics:")
    for name, value in results["retrieval_metrics"].items():
        print(f"  {name}: {value:.4f}")
    print(f"Report: {output_path}")
    print("Diagnostic only: answers are not approved for generation.")


if __name__ == "__main__":
    main()
