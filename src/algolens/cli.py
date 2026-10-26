from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

APPROVED_STATUSES = frozenset({"reviewed", "verified", "approved"})


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(f"Required JSONL file does not exist: {path}")

    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in {path}, line {line_number}.") from exc
            if not isinstance(value, dict):
                raise ValueError(f"Expected a JSON object in {path}, line {line_number}.")
            rows.append(value)
    return rows


def write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    """Write a report atomically so an interrupted run cannot leave partial JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            json.dump(value, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def production_eligible(chunk: dict[str, Any]) -> bool:
    """Require every explicit production approval signal."""
    status = str(chunk.get("review_status", "")).strip().casefold()
    return (
        status in APPROVED_STATUSES
        and chunk.get("eligible_for_answer") is True
        and chunk.get("retrieval_eligible") is True
    )


def load_sources(root: Path) -> dict[str, dict[str, Any]]:
    import yaml

    manifest_path = root / "corpus" / "manifest.yaml"
    from algolens.ingest.manifest import load_manifest

    manifest = load_manifest(manifest_path)
    sources = manifest.get("sources")
    if not isinstance(sources, list):
        raise ValueError("The corpus manifest must contain a sources list.")

    result: dict[str, dict[str, Any]] = {}
    for source in sources:
        if not isinstance(source, dict):
            raise ValueError("Every source manifest record must be a mapping.")
        source_id = source.get("id")
        if not isinstance(source_id, str) or not source_id.strip():
            raise ValueError("Every source must have a nonempty ID.")
        if source_id in result:
            raise ValueError(f"Duplicate source ID in manifest: {source_id}")
        result[source_id] = dict(source)

    # Ensure the manifest remains parseable with the same YAML parser used by
    # the user interface. load_manifest performs the project's validation.
    if not isinstance(yaml.safe_load(manifest_path.read_text(encoding="utf-8")), dict):
        raise ValueError("The corpus manifest is not a YAML mapping.")
    return result


def verify_source_files(
    root: Path,
    sources: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    checked: list[dict[str, Any]] = []
    errors: list[str] = []
    unhashed: list[str] = []
    pending: list[str] = []

    for source_id, record in sources.items():
        local_path = record.get("local_path")
        expected_hash = record.get("sha256")

        if not isinstance(local_path, str) or not local_path.strip():
            pending.append(source_id)
            continue

        path = Path(local_path)
        if not path.is_absolute():
            path = root / path

        if not path.is_file():
            errors.append(f"{source_id}: local source file is missing.")
            continue

        actual_hash = sha256_file(path)
        expected = expected_hash.strip().lower() if isinstance(expected_hash, str) else ""

        if not expected:
            unhashed.append(source_id)
            status = "present_hash_pending"
        elif actual_hash != expected:
            errors.append(f"{source_id}: SHA-256 does not match the manifest.")
            status = "hash_mismatch"
        else:
            status = "hash_verified"

        checked.append(
            {
                "source_id": source_id,
                "path": path.relative_to(root).as_posix()
                if path.is_relative_to(root)
                else str(path),
                "status": status,
                "sha256": actual_hash,
            }
        )

    return {
        "checked": checked,
        "errors": errors,
        "unhashed_sources": unhashed,
        "pending_sources": pending,
    }



def run_reviewed_candidate_check(root: Path) -> int:
    """Audit the approved pages 5-6 candidate against canonical chunks without promoting it."""
    from algolens.ingest.reviewed_candidate import (
        build_reviewed_candidate_chunks,
        validate_candidate_metadata,
    )

    candidate_dir = root / "corpus" / "processed" / "reviewed_candidates"
    metadata_path = candidate_dir / "expectations_printed_pages_5_6.review.json"
    if not metadata_path.is_file():
        raise FileNotFoundError(f"Reviewed-candidate metadata is missing: {metadata_path}")

    metadata_value = json.loads(metadata_path.read_text(encoding="utf-8"))
    if not isinstance(metadata_value, dict):
        raise ValueError("Reviewed-candidate metadata must be a JSON object.")

    candidate_value = metadata_value.get("candidate_markdown_path")
    if not isinstance(candidate_value, str) or not candidate_value.strip():
        raise ValueError("Review metadata must name candidate_markdown_path.")

    candidate_path = (root / candidate_value).resolve()
    resolved_root = root.resolve()
    if not candidate_path.is_relative_to(resolved_root):
        raise ValueError("Candidate Markdown path must remain inside the project root.")
    if not candidate_path.is_file():
        raise FileNotFoundError(f"Reviewed candidate Markdown is missing: {candidate_path}")

    sources = load_sources(root)
    source_id_value = metadata_value.get("source_id")
    if not isinstance(source_id_value, str) or source_id_value not in sources:
        raise ValueError("Reviewed-candidate source_id is absent from the source manifest.")
    source_record = sources[source_id_value]

    source_path_value = source_record.get("local_path")
    if not isinstance(source_path_value, str) or not source_path_value.strip():
        raise ValueError("The source manifest has no local_path for the reviewed source.")
    source_path = Path(source_path_value)
    if not source_path.is_absolute():
        source_path = root / source_path
    if not source_path.is_file():
        raise FileNotFoundError(f"Original source file is missing: {source_path}")

    actual_source_hash = sha256_file(source_path)
    actual_candidate_hash = sha256_file(candidate_path)
    validate_candidate_metadata(
        metadata_value,
        actual_source_sha256=actual_source_hash,
        actual_candidate_sha256=actual_candidate_hash,
    )

    expected_parents, expected_children = build_reviewed_candidate_chunks(
        candidate_path.read_text(encoding="utf-8"),
        source_record,
        source_path=candidate_value.replace("\\\\", "/"),
        artifact_sha256=actual_candidate_hash,
    )

    canonical_parent_path = root / "corpus" / "processed" / "reviewed_chunks" / "parents.jsonl"
    canonical_child_path = root / "corpus" / "processed" / "reviewed_chunks" / "children.jsonl"
    canonical_parents = read_jsonl(canonical_parent_path)
    canonical_children = read_jsonl(canonical_child_path)

    checks: list[dict[str, Any]] = []
    errors: list[str] = []

    def check_level(
        level: str,
        expected_rows: list[dict[str, Any]],
        canonical_rows: list[dict[str, Any]],
    ) -> None:
        canonical_by_id = {str(row.get("chunk_id", "")): row for row in canonical_rows}
        expected_ids = {str(row.get("chunk_id", "")) for row in expected_rows}
        present_ids = expected_ids.intersection(canonical_by_id)
        missing_ids = sorted(expected_ids - present_ids)
        if missing_ids:
            errors.append(f"{level}: canonical corpus is missing expected IDs: {missing_ids}")
        for expected in expected_rows:
            chunk_id = str(expected.get("chunk_id", ""))
            actual = canonical_by_id.get(chunk_id)
            if actual is None:
                continue
            for field in ("source_id", "source_sha256", "artifact_sha256", "pages", "citation"):
                if actual.get(field) != expected.get(field):
                    errors.append(f"{level} {chunk_id}: canonical {field} does not match candidate.")
            if actual.get("review_status") != "approved_retrieval_disabled":
                errors.append(f"{level} {chunk_id}: review status must remain retrieval-disabled.")
            if actual.get("eligible_for_answer") is True or actual.get("retrieval_eligible") is True:
                errors.append(f"{level} {chunk_id}: candidate must not be answer-eligible.")
        checks.append(
            {
                "level": level,
                "expected_count": len(expected_rows),
                "canonical_matching_count": len(present_ids),
                "missing_ids": missing_ids,
            }
        )

    check_level("parents", expected_parents, canonical_parents)
    check_level("children", expected_children, canonical_children)

    report = {
        "status": "reviewed_candidate_audit_passed" if not errors else "reviewed_candidate_audit_failed",
        "candidate_id": metadata_value.get("artifact_id"),
        "source_id": source_id_value,
        "source_sha256": actual_source_hash,
        "candidate_markdown_sha256": actual_candidate_hash,
        "checks": checks,
        "errors": errors,
        "answer_generation_permitted": False,
        "canonical_chunks_modified": False,
        "approval_flags_modified": False,
        "note": (
            "This is an integrity audit only. Owner approval for integration does not enable retrieval."
        ),
    }
    report_path = root / "corpus" / "processed" / "generated" / "reviewed_candidate_audit.json"
    write_json_atomic(report_path, report)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if not errors else 2


def corpus_status(root: Path) -> dict[str, Any]:
    sources = load_sources(root)
    verification = verify_source_files(root, sources)

    child_path = root / "corpus" / "processed" / "reviewed_chunks" / "children.jsonl"
    children = read_jsonl(child_path) if child_path.exists() else []
    approved = [chunk for chunk in children if production_eligible(chunk)]

    question_path = root / "eval" / "gold" / "questions_v0.jsonl"
    questions = read_jsonl(question_path) if question_path.exists() else []

    return {
        "status": (
            "source_integrity_errors"
            if verification["errors"]
            else "safe_mode_pending_approval"
            if not approved
            else "production_corpus_available"
        ),
        "corpus_id": "mit-6.046j-spring-2015-lecture-06",
        "source_verification": verification,
        "reviewed_child_count": len(children),
        "production_eligible_child_count": len(approved),
        "gold_question_count": len(questions),
        "draft_question_count": sum(
            row.get("label_status") == "draft_needs_human_review" for row in questions
        ),
        "note": ("Status checking does not modify source files, chunks, or approvals."),
    }


def run_ingest(root: Path) -> int:
    from algolens.ingest.chunking import parse_pdf_markdown, parse_transcript_jsonl
    from algolens.ingest.pdf import extract_pdf_to_markdown
    from algolens.ingest.transcript import convert_vtt_to_jsonl

    sources = load_sources(root)
    verification = verify_source_files(root, sources)
    if verification["errors"]:
        error_report: dict[str, Any] = {
            "status": "blocked_source_integrity_error",
            "source_verification": verification,
        }
        write_json_atomic(
            root / "corpus" / "processed" / "generated" / "ingest_report.json",
            error_report,
        )
        print(json.dumps(error_report, indent=2))
        return 2

    generated_transcript = (
        root / "corpus" / "processed" / "generated" / "transcript_from_captions.jsonl"
    )
    generated_markdown = root / "corpus" / "experiments" / "cli_ingest" / "L06_TYPED_NOTES.md"

    caption_record = sources.get("L06_YOUTUBE_CAPTIONS")
    notes_record = sources.get("L06_TYPED_NOTES")
    if not caption_record or not notes_record:
        raise ValueError("The manifest must define caption and typed-notes sources.")

    caption_path_value = caption_record.get("local_path")
    notes_path_value = notes_record.get("local_path")
    if not isinstance(caption_path_value, str) or not isinstance(notes_path_value, str):
        raise ValueError("Caption and typed-notes files need local_path values.")

    caption_path = Path(caption_path_value)
    notes_path = Path(notes_path_value)
    if not caption_path.is_absolute():
        caption_path = root / caption_path
    if not notes_path.is_absolute():
        notes_path = root / notes_path

    # Build separate derived artifacts. Do not overwrite the existing canonical
    # transcript, the reviewed candidates, or the original extraction experiments.
    generated_transcript.parent.mkdir(parents=True, exist_ok=True)
    generated_markdown.parent.mkdir(parents=True, exist_ok=True)

    if not generated_transcript.exists():
        convert_vtt_to_jsonl(caption_path, generated_transcript)
    transcript_rows = read_jsonl(generated_transcript)
    transcript_units = parse_transcript_jsonl(generated_transcript.read_text(encoding="utf-8"))
    if not transcript_rows or not transcript_units:
        raise ValueError("Generated caption JSONL contains no usable transcript units.")

    if not generated_markdown.exists():
        extract_pdf_to_markdown(notes_path, generated_markdown)
    markdown = generated_markdown.read_text(encoding="utf-8")
    pdf_units = parse_pdf_markdown(markdown)
    if not pdf_units:
        raise ValueError("Generated PDF Markdown contains no page-aware text units.")

    canonical_transcript = root / "corpus" / "processed" / "transcript.jsonl"
    canonical_count = 0
    if canonical_transcript.exists():
        canonical_units = parse_transcript_jsonl(canonical_transcript.read_text(encoding="utf-8"))
        canonical_count = len(canonical_units)

    report = {
        "status": "ingestion_validation_passed",
        "source_verification": verification,
        "generated_transcript": generated_transcript.relative_to(root).as_posix(),
        "generated_transcript_cue_count": len(transcript_rows),
        "generated_transcript_unit_count": len(transcript_units),
        "generated_pdf_markdown": generated_markdown.relative_to(root).as_posix(),
        "generated_pdf_unit_count": len(pdf_units),
        "existing_canonical_transcript_unit_count": canonical_count,
        "canonical_reviewed_chunks_modified": False,
        "review_approval_flags_modified": False,
        "limitations": [
            "Derived PDF extraction is not automatically approved evidence.",
            "Transcript captions remain unverified against the original video.",
            "This command does not promote any chunk into the answer-eligible corpus.",
        ],
    }
    write_json_atomic(
        root / "corpus" / "processed" / "generated" / "ingest_report.json",
        report,
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


def run_index(root: Path, *, diagnostic: bool, query: str) -> int:
    from algolens.retrieval.bm25 import BM25Index
    from algolens.retrieval.dense import DenseIndex
    from algolens.retrieval.hybrid import HybridIndex
    from algolens.retrieval.pipeline import RetrievalPipeline
    from algolens.retrieval.rerank import CrossEncoderReranker

    if diagnostic:
        corpus_path = root / "corpus" / "experiments" / "chunking" / "children.jsonl"
    else:
        corpus_path = root / "corpus" / "processed" / "reviewed_chunks" / "children.jsonl"

    report_path = root / "index" / "build_report.json"
    if not corpus_path.exists():
        report = {
            "status": "blocked_missing_corpus",
            "corpus_path": str(corpus_path),
            "diagnostic_only": diagnostic,
        }
        write_json_atomic(report_path, report)
        print(json.dumps(report, indent=2))
        return 2

    chunks = read_jsonl(corpus_path)
    eligible = [chunk for chunk in chunks if production_eligible(chunk)]
    if diagnostic:
        build_chunks = chunks
    else:
        build_chunks = eligible

    base_report: dict[str, Any] = {
        "corpus_path": corpus_path.relative_to(root).as_posix(),
        "corpus_sha256": sha256_file(corpus_path),
        "candidate_chunk_count": len(chunks),
        "production_eligible_chunk_count": len(eligible),
        "indexed_chunk_count": len(build_chunks),
        "diagnostic_only": diagnostic,
        "answer_generation_permitted": False if diagnostic else bool(eligible),
        "persistence": ("in-memory; the current index classes do not serialize reusable vectors"),
    }

    if not build_chunks:
        report = {
            **base_report,
            "status": "blocked_no_approved_chunks",
            "message": (
                "No passages have all required approval signals. Review the corpus "
                "first; diagnostic mode is available for retrieval-only experiments."
            ),
        }
        write_json_atomic(report_path, report)
        print(json.dumps(report, indent=2))
        return 2

    try:
        bm25 = BM25Index(build_chunks, include_unreviewed=diagnostic)
        dense = DenseIndex(build_chunks, include_unreviewed=diagnostic)
        hybrid = HybridIndex(
            build_chunks,
            bm25_index=bm25,
            dense_index=dense,
            include_unreviewed=diagnostic,
        )
        reranker = CrossEncoderReranker(include_unreviewed=diagnostic)
        pipeline = RetrievalPipeline(
            hybrid_index=hybrid,
            reranker=reranker,
            candidate_k=20,
            include_unreviewed=diagnostic,
        )
        hits = pipeline.search(query, top_k=5)
    except Exception as exc:
        report = {
            **base_report,
            "status": "index_build_failed",
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
        write_json_atomic(report_path, report)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 1

    report = {
        **base_report,
        "status": "diagnostic_index_smoke_passed" if diagnostic else "index_smoke_passed",
        "query": query,
        "result_count": len(hits),
        "results": [
            {
                "chunk_id": hit.get("chunk_id"),
                "score": hit.get("score"),
                "rerank_score": hit.get("rerank_score"),
                "citation": hit.get("citation"),
                "source_id": hit.get("source_id"),
                "review_status": hit.get("review_status"),
                "eligible_for_answer": production_eligible(hit),
            }
            for hit in hits
        ],
        "note": (
            "Diagnostic results are for retrieval inspection only and must not be "
            "used to generate user-facing answers."
            if diagnostic
            else "This validates index construction; indexes are rebuilt in memory."
        ),
    }
    write_json_atomic(report_path, report)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


def final_evaluation_blockers(root: Path) -> list[str]:
    question_path = root / "eval" / "gold" / "questions_v0.jsonl"
    corpus_path = root / "corpus" / "processed" / "reviewed_chunks" / "children.jsonl"
    blockers: list[str] = []

    if not question_path.exists():
        return ["Gold question file is missing."]

    questions = read_jsonl(question_path)
    if len(questions) != 80:
        blockers.append(f"Expected 80 gold questions; found {len(questions)}.")

    label_counts = Counter(str(row.get("label_status", "<missing>")) for row in questions)
    if any(
        status not in {"reviewed", "verified", "reviewed_or_human_verified"}
        for status in label_counts
    ):
        blockers.append("At least one question still has an unreviewed gold label.")

    split_counts = Counter(str(row.get("split", "<missing>")) for row in questions)
    if split_counts.get("dev", 0) != 50 or split_counts.get("test", 0) != 30:
        blockers.append("A leakage-safe split of exactly 50 dev and 30 test questions is required.")

    if not corpus_path.exists():
        blockers.append("Canonical reviewed child-chunk corpus is missing.")
        return blockers

    chunks = read_jsonl(corpus_path)
    eligible = [chunk for chunk in chunks if production_eligible(chunk)]
    if not eligible:
        blockers.append("No canonical passages are approved for answer generation.")

    known_ids = {str(chunk.get("chunk_id", "")) for chunk in eligible}
    gold_ids = {
        str(passage_id)
        for row in questions
        for passage_id in (
            row.get("gold_passage_ids", [])
            if isinstance(row.get("gold_passage_ids", []), list)
            else []
        )
    }
    missing = sorted(gold_ids - known_ids)
    if missing:
        blockers.append(f"{len(missing)} gold passage IDs do not match the approved corpus.")

    return blockers


def run_eval(root: Path, *, diagnostic: bool, retriever_name: str) -> int:
    question_path = root / "eval" / "gold" / "questions_v0.jsonl"

    if not diagnostic:
        blockers = final_evaluation_blockers(root)
        preflight_report: dict[str, Any] = {
            "status": "blocked_final_evaluation" if blockers else "ready_for_evaluation",
            "diagnostic_only": True,
            "answer_generation_permitted": False,
            "blockers": blockers,
            "note": (
                "The final evaluation command is intentionally blocked until the "
                "gold labels, split, and approved corpus satisfy the required gates."
            ),
        }
        report_path = root / "eval" / "results" / "final_evaluation_preflight.json"
        write_json_atomic(report_path, preflight_report)
        print(json.dumps(preflight_report, indent=2, ensure_ascii=False))
        return 2 if blockers else 0

    from algolens.evaluation.retrieval_metrics import evaluate_rankings
    from algolens.retrieval.bm25 import BM25Index
    from algolens.retrieval.dense import DenseIndex
    from algolens.retrieval.hybrid import HybridIndex
    from algolens.retrieval.pipeline import RetrievalPipeline
    from algolens.retrieval.rerank import CrossEncoderReranker

    corpus_path = root / "corpus" / "experiments" / "chunking" / "children.jsonl"
    if not corpus_path.exists() or not question_path.exists():
        raise FileNotFoundError(
            "Diagnostic evaluation requires the experimental child corpus "
            "and the draft question JSONL."
        )

    chunks = read_jsonl(corpus_path)
    questions = read_jsonl(question_path)
    if not chunks or not questions:
        raise ValueError("Diagnostic corpus and question set must not be empty.")

    bm25 = BM25Index(chunks, include_unreviewed=True)
    from collections.abc import Callable

    search: Callable[[str], list[dict[str, Any]]]
    if retriever_name == "bm25":

        def bm25_search(question: str) -> list[dict[str, Any]]:
            return bm25.search(question, top_k=10)

        search = bm25_search
    elif retriever_name == "dense":
        dense = DenseIndex(chunks, include_unreviewed=True)

        def dense_search(question: str) -> list[dict[str, Any]]:
            return dense.search(question, top_k=10)

        search = dense_search
    else:
        dense = DenseIndex(chunks, include_unreviewed=True)
        hybrid = HybridIndex(
            chunks,
            bm25_index=bm25,
            dense_index=dense,
            include_unreviewed=True,
        )
        if retriever_name == "hybrid":

            def hybrid_search(question: str) -> list[dict[str, Any]]:
                return hybrid.search(question, top_k=10, candidate_k=20)

            search = hybrid_search
        else:
            reranker = CrossEncoderReranker(include_unreviewed=True)
            pipeline = RetrievalPipeline(
                hybrid_index=hybrid,
                reranker=reranker,
                candidate_k=20,
                include_unreviewed=True,
            )

            def reranked_search(question: str) -> list[dict[str, Any]]:
                return pipeline.search(question, top_k=10)

            search = reranked_search

    rankings: dict[str, list[str]] = {}
    for row in questions:
        question_id = str(row.get("question_id", "")).strip()
        question = row.get("question")
        if not question_id or not isinstance(question, str):
            raise ValueError("Each evaluation row needs question_id and question.")
        results = search(question)
        rankings[question_id] = [
            str(result["chunk_id"]) for result in results if result.get("chunk_id")
        ]

    metrics = evaluate_rankings(
        questions,
        rankings,
        k_values=(1, 3, 5, 10),
    )
    report = {
        "status": "exploratory_diagnostic_only",
        "diagnostic_only": True,
        "answer_generation_permitted": False,
        "retriever": retriever_name,
        "corpus_path": corpus_path.relative_to(root).as_posix(),
        "corpus_sha256": sha256_file(corpus_path),
        "question_set_path": question_path.relative_to(root).as_posix(),
        "question_set_sha256": sha256_file(question_path),
        "question_count": len(questions),
        "label_status_counts": dict(
            Counter(str(row.get("label_status", "<missing>")) for row in questions)
        ),
        "retrieval_metrics": metrics,
        "rankings": rankings,
        "limitations": [
            "Question labels are not yet fully human-reviewed.",
            "No approved development/test split is available.",
            "The experimental corpus is not approved answer evidence.",
            "No answer generation or answer-quality score is measured.",
        ],
    }
    report_path = root / "eval" / "results" / f"cli_{retriever_name}_diagnostic.json"
    write_json_atomic(report_path, report)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="algolens",
        description="Safe command-line workflows for the AlgoLens lecture RAG project.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Project root directory (defaults to the repository root).",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("status", help="Inspect source, corpus, and evaluation readiness.")
    commands.add_parser("ingest", help="Verify sources and build separate derived artifacts.")
    commands.add_parser(
        "review-check",
        help="Audit the approved pages 5-6 transcription against canonical chunks without enabling retrieval.",
    )

    index_parser = commands.add_parser("index", help="Build and smoke-test retrieval indexes.")
    index_parser.add_argument(
        "--diagnostic",
        action="store_true",
        help="Use experimental, unapproved chunks for retrieval-only diagnostics.",
    )
    index_parser.add_argument(
        "--smoke-query",
        default="How does randomized Quicksort achieve expected n log n running time?",
    )

    eval_parser = commands.add_parser("eval", help="Check final-evaluation readiness.")
    eval_parser.add_argument(
        "--diagnostic",
        action="store_true",
        help="Run exploratory retrieval metrics on the experimental corpus.",
    )
    eval_parser.add_argument(
        "--retriever",
        choices=("bm25", "dense", "hybrid", "hybrid-reranked"),
        default="bm25",
        help="Retriever for diagnostic evaluation.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = (args.root or project_root()).resolve()

    try:
        if args.command == "status":
            report = corpus_status(root)
            print(json.dumps(report, indent=2, ensure_ascii=False))
            return 2 if report["status"] == "source_integrity_errors" else 0
        if args.command == "ingest":
            return run_ingest(root)
        if args.command == "review-check":
            return run_reviewed_candidate_check(root)
        if args.command == "index":
            return run_index(root, diagnostic=args.diagnostic, query=args.smoke_query)
        if args.command == "eval":
            return run_eval(
                root,
                diagnostic=args.diagnostic,
                retriever_name=args.retriever,
            )
        raise ValueError(f"Unsupported command: {args.command}")
    except Exception as exc:
        # Keep failures actionable without dumping credentials or environment values.
        print(f"AlgoLens command failed: {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
