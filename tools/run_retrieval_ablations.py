from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any

from algolens.cli import read_jsonl, sha256_file, write_json_atomic
from algolens.evaluation.retrieval_metrics import evaluate_rankings
from algolens.retrieval.bm25 import BM25Index, reciprocal_rank_fusion
from algolens.retrieval.dense import DenseIndex


def summary(metrics: dict[str, Any]) -> dict[str, float]:
    values = metrics["retrieval_metrics"]
    return {
        "question_recall@1": float(values["question_recall@1"]),
        "question_recall@3": float(values["question_recall@3"]),
        "question_recall@5": float(values["question_recall@5"]),
        "question_recall@10": float(values["question_recall@10"]),
        "fractional_recall@5": float(values["recall@5"]),
        "mrr@10": float(values["mrr@10"]),
        "ndcg@10": float(values["ndcg@10"]),
    }


def evaluate(
    questions: list[dict[str, Any]], rankings: dict[str, list[str]]
) -> dict[str, Any]:
    overall = evaluate_rankings(questions, rankings, k_values=(1, 3, 5, 10))
    return {
        "overall": summary(overall),
        "dev": summary(
            evaluate_rankings(
                [row for row in questions if row.get("split") == "dev"],
                rankings,
                k_values=(1, 3, 5, 10),
            )
        ),
        "test": summary(
            evaluate_rankings(
                [row for row in questions if row.get("split") == "test"],
                rankings,
                k_values=(1, 3, 5, 10),
            )
        ),
    }


def query_rankings(index: Any, questions: list[dict[str, Any]], *, top_k: int) -> dict[str, list[str]]:
    return {
        str(row["question_id"]): [
            str(hit["chunk_id"]) for hit in index.search(str(row["question"]), top_k=top_k)
        ]
        for row in questions
    }


def markdown_report(report: dict[str, Any]) -> str:
    runs = sorted(
        report["runs"],
        key=lambda row: (
            -row["metrics"]["test"]["question_recall@5"],
            -row["metrics"]["test"]["mrr@10"],
            row["name"],
        ),
    )
    lines = [
        "# AlgoLens retrieval ablations",
        "",
        f"Corpus SHA-256: `{report['corpus_sha256']}`  ",
        f"Question set SHA-256: `{report['question_set_sha256']}`  ",
        f"Completed runs: **{len(runs)}**",
        "",
        "`question_recall@5` counts a question when at least one labelled passage appears "
        "in the first five results. `fractional_recall@5` averages the fraction of all "
        "labelled passages recovered for each question.",
        "",
        "| Run | Test question recall@5 | Test fractional recall@5 | Test MRR@10 | Overall question recall@5 |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in runs:
        test = row["metrics"]["test"]
        overall = row["metrics"]["overall"]
        lines.append(
            f"| {row['name']} | {test['question_recall@5']:.3f} | "
            f"{test['fractional_recall@5']:.3f} | {test['mrr@10']:.3f} | "
            f"{overall['question_recall@5']:.3f} |"
        )
    lines.extend(
        [
            "",
            "The saved test split is version-controlled, so it is a held-out workflow split "
            "rather than a secret benchmark. Question labels received AI-assisted source "
            "review and should be independently reviewed before making a stronger claim.",
            "",
        ]
    )
    return "\n".join(lines)


def write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="\n", dir=path.parent, delete=False
    ) as handle:
        temporary = Path(handle.name)
        handle.write(text)
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run reproducible AlgoLens retrieval ablations.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.root.resolve()
    corpus_path = root / "corpus/processed/reviewed_chunks/children.jsonl"
    questions_path = root / "eval/gold/questions_v1_reviewed.jsonl"
    chunks = read_jsonl(corpus_path)
    questions = read_jsonl(questions_path)
    runs: list[dict[str, Any]] = []

    default_bm25_rankings: dict[str, list[str]] | None = None
    for k1 in (0.8, 1.2, 1.5, 2.0):
        for b in (0.25, 0.5, 0.75, 1.0):
            index = BM25Index(chunks, k1=k1, b=b)
            rankings = query_rankings(index, questions, top_k=30)
            if k1 == 1.5 and b == 0.75:
                default_bm25_rankings = rankings
            runs.append(
                {
                    "name": f"bm25-k1-{k1}-b-{b}",
                    "family": "bm25",
                    "parameters": {"k1": k1, "b": b},
                    "metrics": evaluate(questions, rankings),
                }
            )
    if default_bm25_rankings is None:
        raise RuntimeError("Default BM25 ranking was not generated.")

    dense = DenseIndex(chunks)
    dense_rankings = query_rankings(dense, questions, top_k=30)
    runs.append(
        {
            "name": "dense-default",
            "family": "dense",
            "parameters": {"model": dense.model_name},
            "metrics": evaluate(questions, dense_rankings),
        }
    )

    for rrf_k in (10, 30, 60, 100):
        for candidate_k in (10, 20, 30):
            rankings: dict[str, list[str]] = {}
            for row in questions:
                question_id = str(row["question_id"])
                fused = reciprocal_rank_fusion(
                    [
                        default_bm25_rankings[question_id][:candidate_k],
                        dense_rankings[question_id][:candidate_k],
                    ],
                    k=rrf_k,
                )
                rankings[question_id] = [str(item["chunk_id"]) for item in fused]
            runs.append(
                {
                    "name": f"hybrid-rrf-{rrf_k}-candidates-{candidate_k}",
                    "family": "hybrid",
                    "parameters": {"rrf_k": rrf_k, "candidate_k": candidate_k},
                    "metrics": evaluate(questions, rankings),
                }
            )

    for name in ("hybrid-reranked", "hybrid-reranked-paired"):
        path = root / f"eval/results/final_{name}.json"
        saved = json.loads(path.read_text(encoding="utf-8"))
        rankings = {
            str(question_id): [str(passage_id) for passage_id in passage_ids]
            for question_id, passage_ids in saved["rankings"].items()
        }
        runs.append(
            {
                "name": name,
                "family": "reranked",
                "parameters": {"pairing": name.endswith("paired")},
                "metrics": evaluate(questions, rankings),
            }
        )

    report = {
        "status": "retrieval_ablations_completed",
        "run_count": len(runs),
        "corpus_sha256": sha256_file(corpus_path),
        "question_set_sha256": sha256_file(questions_path),
        "question_count": len(questions),
        "runs": runs,
        "limitations": [
            "Question labels received AI-assisted source review rather than independent human annotation.",
            "The test split is version-controlled and is not a secret benchmark.",
            "Reranked rows reuse saved inference rankings for the same corpus and question hashes.",
        ],
    }
    output_dir = root / "eval/results"
    write_json_atomic(output_dir / "retrieval_ablations.json", report)
    write_text_atomic(output_dir / "retrieval_ablations.md", markdown_report(report))
    print(
        json.dumps(
            {
                "status": report["status"],
                "run_count": report["run_count"],
                "json": "eval/results/retrieval_ablations.json",
                "markdown": "eval/results/retrieval_ablations.md",
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
