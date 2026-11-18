from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from algolens.cli import read_jsonl, sha256_file, write_json_atomic
from algolens.evaluation.generation_metrics import evaluate_generation_rows
from algolens.providers import OpenAICompatibleProvider
from app.app import build_runtime


def estimated_tokens(text: str) -> int:
    return max(1, (len(text) + 3) // 4)


def current_system_row(service: Any, question: dict[str, Any]) -> dict[str, Any]:
    answer = service.answer(str(question["question"]))
    citations = sorted({citation for claim in answer.claims for citation in claim.cites})
    evidence_text = "\n".join(hit.passage.text for hit in answer.sources)
    provider_called = int(bool(answer.claims) or answer.status == "sources_only")
    return {
        "question_id": question["question_id"],
        "question": question["question"],
        "answerable": question["answerable"],
        "key_points": question["key_points"],
        "gold_passage_ids": question["gold_passage_ids"],
        "status": answer.status,
        "answer_md": answer.answer_md,
        "citation_ids": citations,
        "claims": [
            {"text": claim.text, "cites": claim.cites, "support": claim.support}
            for claim in answer.claims
        ],
        "claim_support": [claim.support for claim in answer.claims],
        "source_ids": [hit.passage.id for hit in answer.sources],
        "latency_ms": answer.latency_ms,
        "provider_calls": provider_called,
        "estimated_input_tokens": estimated_tokens(str(question["question"]) + evidence_text),
        "estimated_output_tokens": estimated_tokens(answer.answer_md),
        "model": answer.model,
    }


def no_retrieval_row(
    provider: OpenAICompatibleProvider,
    question: dict[str, Any],
    *,
    retries: int = 6,
) -> dict[str, Any]:
    """Call the same generator without evidence to quantify the hallucination baseline."""
    payload: dict[str, Any] = {
        "model": provider.model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Answer the algorithm question from memory in at most 120 words. "
                    "Do not claim to have lecture citations. If unsure, say so."
                ),
            },
            {"role": "user", "content": str(question["question"])},
        ],
        "temperature": 0,
        "max_completion_tokens": 512,
    }
    if "api.groq.com" in provider.base_url:
        payload["reasoning_effort"] = "low"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "AlgoLens/0.1.0",
    }
    if provider.api_key:
        headers["Authorization"] = f"Bearer {provider.api_key}"
    request = urllib.request.Request(
        f"{provider.base_url}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    started = time.perf_counter()
    result: dict[str, Any] | None = None
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=provider.timeout_seconds) as response:
                value = json.loads(response.read().decode("utf-8"))
            if not isinstance(value, dict):
                raise ValueError("Provider response must be a JSON object.")
            result = value
            break
        except urllib.error.HTTPError as exc:
            if exc.code != 429 or attempt >= retries:
                raise
            retry_after = exc.headers.get("Retry-After")
            try:
                wait_seconds = float(retry_after) if retry_after else 2.0 ** (attempt + 1)
            except ValueError:
                wait_seconds = 2.0 ** (attempt + 1)
            time.sleep(min(30.0, max(1.0, wait_seconds)))
    if result is None:
        raise RuntimeError("Provider retry loop ended without a response.")
    latency_ms = (time.perf_counter() - started) * 1000.0
    answer = str(result["choices"][0]["message"].get("content") or "").strip()
    usage = result.get("usage", {}) if isinstance(result, dict) else {}
    return {
        "question_id": question["question_id"],
        "question": question["question"],
        "answerable": question["answerable"],
        "key_points": question["key_points"],
        "gold_passage_ids": question["gold_passage_ids"],
        "status": "answered" if answer else "abstained",
        "answer_md": answer or "The baseline returned no answer.",
        "citation_ids": [],
        "claim_support": [],
        "source_ids": [],
        "latency_ms": latency_ms,
        "provider_calls": 1,
        "estimated_input_tokens": int(
            usage.get("prompt_tokens", estimated_tokens(str(question["question"])))
        ),
        "estimated_output_tokens": int(
            usage.get("completion_tokens", estimated_tokens(answer or "no answer"))
        ),
        "model": provider.model,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate generated answers and the no-retrieval hallucination baseline."
    )
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--split", choices=("dev", "test", "all"), default="test")
    parser.add_argument("--mode", choices=("current", "no-retrieval", "all"), default="all")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--delay-seconds", type=float, default=1.0)
    parser.add_argument(
        "--metrics-only",
        action="store_true",
        help="Recompute aggregate metrics from existing rows without provider calls.",
    )
    args = parser.parse_args()
    root = args.root.resolve()
    question_path = root / "eval/gold/questions_v1_reviewed.jsonl"
    corpus_path = root / "corpus/processed/reviewed_chunks/children.jsonl"
    questions = read_jsonl(question_path)
    if args.split != "all":
        questions = [row for row in questions if row.get("split") == args.split]
    if args.limit is not None:
        if args.limit < 1:
            raise ValueError("--limit must be positive.")
        questions = questions[: args.limit]

    output_dir = root / "eval/results"
    completed: list[str] = []
    if args.metrics_only:
        modes = ("current", "no-retrieval") if args.mode == "all" else (args.mode,)
        for mode in modes:
            label = "current" if mode == "current" else "no_retrieval"
            path = output_dir / f"generation_{label}_{args.split}.json"
            report = json.loads(path.read_text(encoding="utf-8"))
            rows = report.get("rows") if isinstance(report, dict) else None
            if not isinstance(rows, list) or not rows:
                raise ValueError(f"Existing report has no rows: {path}")
            report["metrics"] = evaluate_generation_rows(rows)
            write_json_atomic(path, report)
            completed.append(path.relative_to(root).as_posix())
        print(json.dumps({"status": "completed", "reports": completed}, indent=2))
        return 0

    if args.mode in {"current", "all"}:
        service, readiness = build_runtime()
        if service is None:
            raise RuntimeError(f"Grounded runtime unavailable: {readiness.get('message')}")
        rows = []
        for question in questions:
            rows.append(current_system_row(service, question))
            if args.delay_seconds > 0:
                time.sleep(min(30.0, args.delay_seconds))
        report = {
            "status": "generation_evaluation_completed",
            "system": "algolens_grounded",
            "split": args.split,
            "corpus_sha256": sha256_file(corpus_path),
            "question_set_sha256": sha256_file(question_path),
            "metrics": evaluate_generation_rows(rows),
            "rows": rows,
        }
        path = output_dir / f"generation_current_{args.split}.json"
        write_json_atomic(path, report)
        completed.append(path.relative_to(root).as_posix())

    if args.mode in {"no-retrieval", "all"}:
        provider = OpenAICompatibleProvider.from_env()
        path = output_dir / f"generation_no_retrieval_{args.split}.json"
        existing = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        existing_rows = existing.get("rows", []) if isinstance(existing, dict) else []
        rows = [row for row in existing_rows if isinstance(row, dict)]
        completed_ids = {str(row.get("question_id")) for row in rows}
        base_report = {
            "system": "no_retrieval_llm",
            "split": args.split,
            "question_set_sha256": sha256_file(question_path),
            "limitations": [
                "This baseline intentionally has no lecture evidence or citations.",
                "Correctness uses deterministic key-point coverage, not a second-family judge.",
            ],
        }
        for question in questions:
            if str(question["question_id"]) in completed_ids:
                continue
            rows.append(no_retrieval_row(provider, question))
            checkpoint = {
                **base_report,
                "status": "generation_evaluation_in_progress",
                "metrics": evaluate_generation_rows(rows),
                "rows": rows,
            }
            write_json_atomic(path, checkpoint)
            if args.delay_seconds > 0:
                time.sleep(min(30.0, args.delay_seconds))
        report = {
            **base_report,
            "status": "generation_evaluation_completed",
            "metrics": evaluate_generation_rows(rows),
            "rows": rows,
        }
        write_json_atomic(path, report)
        completed.append(path.relative_to(root).as_posix())

    print(json.dumps({"status": "completed", "reports": completed}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
