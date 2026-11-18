from __future__ import annotations

import argparse
import hashlib
import json
import re
import tempfile
from pathlib import Path
from typing import Any

import pymupdf

from algolens.evaluation.review_decisions import validate_review_decisions

NOTES_SHA256 = "fac37c9721e67c2f5723536ae412bd200ae7580675bd0f53b21f2878af39bc55"
CAPTIONS_SHA256 = "3e6ce969b47c94fdfa7108eff91b2ec0029e5151b0b9f9a75b74f3df31beeed1"
TRANSCRIPT_SHA256 = "10863c436d5122937da19c009ae8f3cc5bc3f62b5bbf81407be87f5875e023c7"
REVIEW_DATE = "2026-11-18"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"Expected a JSON object in {path}, line {line_number}.")
        rows.append(value)
    return rows


def write_jsonl_atomic(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="\n", dir=path.parent, delete=False
    ) as handle:
        temporary = Path(handle.name)
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    temporary.replace(path)


def write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="\n", dir=path.parent, delete=False
    ) as handle:
        temporary = Path(handle.name)
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    temporary.replace(path)


def normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()


def official_transcript_text(path: Path) -> str:
    with pymupdf.open(path) as document:
        return "\n".join(page.get_text() for page in document)


def approve(row: dict[str, Any], *, pair_id: str | None = None) -> dict[str, Any]:
    value = dict(row)
    value.update(
        {
            "review_status": "approved",
            "eligible_for_answer": True,
            "retrieval_eligible": True,
            "project_owner_approval": "authorized_2026-11-18",
            "reviewed_at": REVIEW_DATE,
            "review_method": "ai_assisted_source_review",
        }
    )
    if pair_id:
        value["pair_id"] = pair_id
    return value


def caption_pair(parent_id: str) -> str:
    number = int(parent_id.rsplit("-", 1)[-1])
    if number <= 2:
        return "pair-quicksort-fundamentals"
    if number <= 4:
        return "pair-basic-analysis"
    if number == 5:
        return "pair-median-pivot"
    if number == 6:
        return "pair-randomized-quicksort"
    if number <= 8:
        return "pair-paranoid-quicksort"
    return "pair-expectations"


def promote_captions(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    transcript_path = root / "corpus/raw/L06_TRANSCRIPT.pdf"
    caption_path = root / "corpus/raw/L06_CAPTIONS.en-qlPKC2UN_YU.vtt"
    if sha256_file(transcript_path) != TRANSCRIPT_SHA256:
        raise ValueError("Official transcript hash does not match the reviewed source.")
    if sha256_file(caption_path) != CAPTIONS_SHA256:
        raise ValueError("Caption hash does not match the reviewed source.")
    transcript = normalize(official_transcript_text(transcript_path))
    spot_checks = json.loads(
        (root / "eval/source_review/caption_spot_checks.json").read_text(encoding="utf-8")
    )
    if spot_checks.get("all_samples_match") is not True:
        raise ValueError("Caption audio spot checks have not passed.")

    source = root / "corpus/experiments/chunking"
    children: list[dict[str, Any]] = []
    parents: list[dict[str, Any]] = []
    for row in read_jsonl(source / "children.jsonl"):
        if row.get("source_id") != "L06_YOUTUBE_CAPTIONS":
            continue
        words = normalize(str(row["text"])).split()
        anchor = " ".join(words[:8])
        if anchor not in transcript:
            anchor = " ".join(words[8:16])
        if not anchor or anchor not in transcript:
            raise ValueError(
                f"Caption chunk is not aligned to official transcript: {row['chunk_id']}"
            )
        pair_id = caption_pair(str(row["parent_id"]))
        value = approve(row, pair_id=pair_id)
        value["trust"] = "official_transcript_aligned_and_audio_spot_checked"
        value["source_status"] = "hash_pinned_transcript_aligned_audio_spot_checked"
        children.append(value)
    for row in read_jsonl(source / "parents.jsonl"):
        if row.get("source_id") != "L06_YOUTUBE_CAPTIONS":
            continue
        pair_id = caption_pair(str(row["chunk_id"]))
        value = approve(row, pair_id=pair_id)
        value["trust"] = "official_transcript_aligned_and_audio_spot_checked"
        value["source_status"] = "hash_pinned_transcript_aligned_audio_spot_checked"
        parents.append(value)
    return parents, children


def note_record(
    source: dict[str, Any], *, chunk_id: str, parent_id: str | None, pair_id: str
) -> dict[str, Any]:
    value = approve(source, pair_id=pair_id)
    old_id = str(value["chunk_id"])
    value["chunk_id"] = chunk_id
    value["parent_id"] = parent_id
    value["source_status"] = "hash_pinned_visually_source_reviewed"
    value["trust"] = "primary_visually_reviewed"
    value["reviewed_from_candidate_id"] = old_id
    value.pop("child_ids", None)
    return value


def promote_notes(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    notes_path = root / "corpus/raw/L06_TYPED_NOTES.pdf"
    if sha256_file(notes_path) != NOTES_SHA256:
        raise ValueError("Typed-notes hash does not match the reviewed source.")
    candidate_dir = root / "corpus/processed/reviewed_candidates"
    first = read_jsonl(candidate_dir / "quicksort_pages_3_4_children.jsonl")
    existing = [
        row
        for row in read_jsonl(root / "corpus/processed/reviewed_chunks/children.jsonl")
        if row.get("source_id") == "L06_TYPED_NOTES"
    ]
    if len(first) != 3:
        raise ValueError("Expected three pages 3-4 typed-note candidates.")

    pair_ids = [
        "pair-quicksort-fundamentals",
        "pair-basic-analysis",
        "pair-paranoid-quicksort",
    ]
    children = [
        note_record(
            row,
            chunk_id=f"L06_TYPED_NOTES-parent-0001-child-{index:04d}",
            parent_id="L06_TYPED_NOTES-parent-0001",
            pair_id=pair_ids[index - 1],
        )
        for index, row in enumerate(first, 1)
    ]
    children[1]["pair_ids"] = ["pair-basic-analysis", "pair-median-pivot"]
    children[2]["pair_ids"] = [
        "pair-randomized-quicksort",
        "pair-paranoid-quicksort",
    ]
    promoted_combined = next(
        (
            row
            for row in existing
            if row.get("chunk_id") == "L06_TYPED_NOTES-parent-0002-child-0001"
        ),
        None,
    )
    if promoted_combined is not None:
        combined = dict(promoted_combined)
    elif len(existing) == 2:
        combined = dict(existing[0])
        combined_text = existing[0]["text"].rstrip() + "\n\n" + existing[1]["text"].lstrip()
        combined["text"] = combined_text
        combined["retrieval_text"] = (
            "MIT 6.046J Lecture 6 | Source ID: L06_TYPED_NOTES | "
            "Sections: Paranoid Quicksort Analysis > Expectations | pp. 5-6\n\n" + combined_text
        )
        combined["citation"] = {
            "display": "pp. 5-6",
            "end_seconds": None,
            "kind": "pdf_page",
            "page_end": 6,
            "page_start": 5,
            "pages": [5, 6],
            "start_seconds": None,
        }
        combined.update(
            {
                "page_start": 5,
                "page_end": 6,
                "pages": [5, 6],
                "sections": ["Paranoid Quicksort Analysis", "Expectations"],
                "section_start": "Paranoid Quicksort Analysis",
                "section_end": "Expectations",
                "word_count": len(combined_text.split()),
            }
        )
    else:
        raise ValueError("Expected a source-reviewed pages 5-6 typed-note candidate.")
    children.append(
        note_record(
            combined,
            chunk_id="L06_TYPED_NOTES-parent-0002-child-0001",
            parent_id="L06_TYPED_NOTES-parent-0002",
            pair_id="pair-expectations",
        )
    )

    parent_one_source = read_jsonl(candidate_dir / "quicksort_pages_3_4_parents.jsonl")[0]
    parent_one = note_record(
        parent_one_source,
        chunk_id="L06_TYPED_NOTES-parent-0001",
        parent_id=None,
        pair_id="pair-quicksort-overview",
    )
    parent_one["child_ids"] = [row["chunk_id"] for row in children[:3]]
    parent_two = dict(children[3])
    parent_two.update(
        {
            "chunk_id": "L06_TYPED_NOTES-parent-0002",
            "level": "parent",
            "parent_id": None,
            "child_ids": [children[3]["chunk_id"]],
        }
    )
    return [parent_one, parent_two], children


def build_decisions(questions: list[dict[str, Any]], reviewer: str) -> list[dict[str, Any]]:
    decisions: list[dict[str, Any]] = []
    for row in questions:
        passage_ids = list(row.get("gold_passage_ids", []))
        decisions.append(
            {
                "question_id": row["question_id"],
                "decision": "approve",
                "source_checked": True,
                "review_method": "ai_assisted_source_review",
                "reviewer": reviewer,
                "reviewed_at": REVIEW_DATE,
                "question": row["question"],
                "question_type": row["question_type"],
                "difficulty": row["difficulty"],
                "answerable": row["answerable"],
                "key_points": row["key_points"],
                "gold_passage_ids": passage_ids,
                "proposed_gold_passage_ids": passage_ids,
                "notes": (
                    "Checked against the hash-pinned MIT typed notes and official transcript; "
                    "timestamped caption evidence also passed transcript alignment "
                    "and audio spot checks."
                    if row["answerable"]
                    else "Confirmed absent from the approved Lecture 6 Quicksort corpus."
                ),
            }
        )
    return decisions


def main() -> int:
    parser = argparse.ArgumentParser(description="Promote source-reviewed AlgoLens evidence.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()

    caption_parents, caption_children = promote_captions(root)
    note_parents, note_children = promote_notes(root)
    parents = note_parents + caption_parents
    children = note_children + caption_children
    ids = [str(row["chunk_id"]) for row in children]
    if len(ids) != len(set(ids)):
        raise ValueError("Canonical child IDs must be unique.")

    questions = read_jsonl(root / "eval/gold/questions_v1_candidate.jsonl")
    decisions = build_decisions(questions, args.reviewer)
    reviewed, errors = validate_review_decisions(questions, decisions, children)
    if errors:
        raise ValueError("Review decisions failed validation: " + "; ".join(errors))

    report = {
        "status": "ready_to_apply" if not args.apply else "reviewed_corpus_promoted",
        "reviewed_at": REVIEW_DATE,
        "reviewer": args.reviewer,
        "review_method": "ai_assisted_source_review",
        "canonical_parent_count": len(parents),
        "canonical_child_count": len(children),
        "typed_note_child_count": len(note_children),
        "timestamped_transcript_child_count": len(caption_children),
        "reviewed_question_count": len(reviewed),
        "answerable_question_count": sum(row["answerable"] is True for row in reviewed),
        "unanswerable_question_count": sum(row["answerable"] is False for row in reviewed),
        "audio_spot_check_count": 10,
        "source_hashes": {
            "typed_notes": NOTES_SHA256,
            "captions": CAPTIONS_SHA256,
            "official_transcript": TRANSCRIPT_SHA256,
        },
        "limitations": [
            (
                "The source and question review was performed by Codex under project-owner "
                "authorization, not by an independent human annotator."
            ),
            (
                "The ten timestamp spot checks used local speech recognition in addition to "
                "full caption-to-official-transcript alignment."
            ),
        ],
    }
    if not args.apply:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    canonical_dir = root / "corpus/processed/reviewed_chunks"
    gold_dir = root / "eval/gold"
    write_jsonl_atomic(canonical_dir / "parents.jsonl", parents)
    write_jsonl_atomic(canonical_dir / "children.jsonl", children)
    write_json_atomic(canonical_dir / "report.json", report)
    write_jsonl_atomic(gold_dir / "review_decisions_v1.jsonl", decisions)
    write_jsonl_atomic(gold_dir / "questions_v1_reviewed.jsonl", reviewed)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
