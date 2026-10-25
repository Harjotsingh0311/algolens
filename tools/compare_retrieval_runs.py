from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "eval" / "results"

REPORTS = {
    "BM25": RESULTS / "bm25_draft.json",
    "Dense": RESULTS / "dense_draft.json",
    "Hybrid RRF": RESULTS / "hybrid-rff_draft.json",
}

METRICS = (
    "recall@1",
    "recall@3",
    "recall@5",
    "recall@10",
    "mrr@10",
    "ndcg@10",
)


def load_report(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"Missing evaluation report: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("diagnostic_only") is not True:
        raise ValueError(f"{path.name} is not marked diagnostic_only.")
    if "retrieval_metrics" not in data:
        raise ValueError(f"{path.name} has no retrieval_metrics.")
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare AlgoLens provisional retrieval reports.")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    reports = {name: load_report(path) for name, path in REPORTS.items()}

    for field in (
        "question_set_sha256",
        "corpus_sha256",
        "answerable_question_count",
        "unanswerable_question_count",
    ):
        values = {report.get(field) for report in reports.values()}
        if len(values) != 1:
            raise ValueError(f"Reports do not share the same {field}: {values}")

    if any(
        report.get("evaluation_status") != "provisional_draft_labels" for report in reports.values()
    ):
        raise ValueError("Expected all three reports to be provisional draft-label runs.")

    metrics_by_model = {name: report["retrieval_metrics"] for name, report in reports.items()}

    lines = [
        "# AlgoLens Retrieval Comparison — Draft v0",
        "",
        "> **Provisional diagnostic only.** Labels and corpus passages still "
        "require human verification. Do not present this as final performance.",
        "",
        "## Experimental consistency",
        "",
        f"- Answerable questions scored: "
        f"{next(iter(reports.values()))['answerable_question_count']}",
        f"- Unanswerable questions excluded from retrieval ranking metrics: "
        f"{next(iter(reports.values()))['unanswerable_question_count']}",
        f"- Question-set SHA-256: `{next(iter(reports.values()))['question_set_sha256']}`",
        f"- Corpus SHA-256: `{next(iter(reports.values()))['corpus_sha256']}`",
        "- All three reports passed the hash consistency checks.",
        "",
        "## Aggregate metrics",
        "",
        "| Metric | BM25 | Dense | Hybrid RRF | Best observed |",
        "|---|---:|---:|---:|---|",
    ]

    for metric in METRICS:
        values = {name: float(metrics_by_model[name][metric]) for name in REPORTS}
        best_value = max(values.values())
        winners = [name for name, value in values.items() if abs(value - best_value) < 1e-12]
        cells = [f"{values[name]:.4f}" for name in REPORTS]
        lines.append(f"| {metric} | {cells[0]} | {cells[1]} | {cells[2]} | {', '.join(winners)} |")

    baseline = metrics_by_model["BM25"]
    lines += [
        "",
        "## Delta relative to BM25",
        "",
        "Positive values mean the other retriever scored higher on that metric.",
        "",
        "| Metric | Dense − BM25 | Hybrid RRF − BM25 |",
        "|---|---:|---:|",
    ]

    for metric in METRICS:
        dense_delta = float(metrics_by_model["Dense"][metric]) - float(baseline[metric])
        hybrid_delta = float(metrics_by_model["Hybrid RRF"][metric]) - float(baseline[metric])
        lines.append(f"| {metric} | {dense_delta:+.4f} | {hybrid_delta:+.4f} |")

    lines += [
        "",
        "## Provisional interpretation",
        "",
        "- Keep BM25 as the initial retrieval baseline: it has the highest "
        "observed Recall@5, Recall@10, MRR@10, and nDCG@10.",
        "- Keep Hybrid RRF for follow-up experiments: it has the highest "
        "observed Recall@1 and Recall@3.",
        "- Dense-only retrieval scored below the other methods on these draft labels in this run.",
        "- These observations are limited to this small, unreviewed corpus "
        "and draft question set. They do not establish general superiority.",
        "- The current evaluation does not measure answer correctness, "
        "faithfulness, citation quality, abstention, latency, or reranking.",
        "",
        "## Metric definitions",
        "",
        "- **Recall@k:** fraction of labeled relevant passages retrieved in "
        "the first k results, averaged over answerable questions.",
        "- **MRR@10:** average reciprocal rank of the first relevant passage within the top 10.",
        "- **nDCG@10:** ranking quality with binary passage relevance.",
        "",
        "Unanswerable questions are counted, not scored by these retrieval "
        "metrics. Abstention needs a separate evaluation.",
        "",
    ]

    output = RESULTS / "retrieval_comparison_draft.md"
    if output.exists() and not args.overwrite:
        raise SystemExit(f"{output} already exists. Inspect it or rerun with --overwrite.")

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="utf-8")

    print("All three reports use identical question-set and corpus hashes.")
    print("Provisional comparison:")
    for metric in METRICS:
        values = metrics_by_model
        best = max(REPORTS, key=lambda name: float(values[name][metric]))
        print(f"  {metric}: best observed = {best} ({values[best][metric]:.4f})")
    print(f"Comparison report: {output}")


if __name__ == "__main__":
    main()
