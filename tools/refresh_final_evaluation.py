from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from algolens.cli import read_jsonl, sha256_file, write_json_atomic
from algolens.evaluation.answerability_metrics import evaluate_answerability_scores
from algolens.evaluation.retrieval_metrics import evaluate_rankings


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Refresh saved final retrieval metrics without rerunning model inference."
    )
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.root.resolve()
    questions_path = root / "eval/gold/questions_v1_reviewed.jsonl"
    corpus_path = root / "corpus/processed/reviewed_chunks/children.jsonl"
    questions = read_jsonl(questions_path)
    refreshed: list[str] = []

    for path in sorted((root / "eval/results").glob("final_*.json")):
        if path.name == "final_evaluation_preflight.json":
            continue
        report: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        rankings = report.get("rankings")
        if not isinstance(rankings, dict):
            continue
        normalized = {
            str(question_id): [str(passage_id) for passage_id in passage_ids]
            for question_id, passage_ids in rankings.items()
            if isinstance(passage_ids, list)
        }
        report["retrieval_metrics"] = evaluate_rankings(
            questions, normalized, k_values=(1, 3, 5, 10)
        )
        report["retrieval_metrics_by_split"] = {
            split: evaluate_rankings(
                [row for row in questions if row.get("split") == split],
                normalized,
                k_values=(1, 3, 5, 10),
            )
            for split in ("dev", "test")
        }
        answerability = report.get("answerability")
        if isinstance(answerability, dict) and isinstance(answerability.get("top_scores"), dict):
            top_scores = answerability["top_scores"]
            answer_threshold = float(answerability["answer_threshold"])
            partial_threshold = float(answerability["partial_threshold"])
            for split in ("dev", "test"):
                rows = [row for row in questions if row.get("split") == split]
                refreshed_answerability = evaluate_answerability_scores(
                    answerable=[bool(row["answerable"]) for row in rows],
                    top_scores=[top_scores.get(str(row["question_id"])) for row in rows],
                    answer_threshold=answer_threshold,
                    partial_threshold=partial_threshold,
                )
                refreshed_answerability["thresholds_calibrated"] = True
                answerability[split] = refreshed_answerability
        report["corpus_sha256"] = sha256_file(corpus_path)
        report["question_set_sha256"] = sha256_file(questions_path)
        write_json_atomic(path, report)
        refreshed.append(path.relative_to(root).as_posix())

    print(json.dumps({"status": "refreshed", "reports": refreshed}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
