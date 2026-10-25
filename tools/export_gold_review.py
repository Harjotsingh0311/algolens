from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
QUESTIONS_PATH = ROOT / "eval" / "gold" / "questions_v0.jsonl"
CHUNKS_PATH = ROOT / "corpus" / "experiments" / "chunking" / "children.jsonl"
DEFAULT_OUTPUT = ROOT / "eval" / "gold" / "review_v0.md"

SUSPICIOUS_STRINGS = ("â€“", "â€œ", "â€", "Ã", "Â", "\ufffd")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(f"Required input file does not exist: {path}")

    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON at {path}, line {line_number}: {exc}") from exc

        if not isinstance(row, dict):
            raise ValueError(f"Expected JSON object at {path}, line {line_number}")
        rows.append(row)

    return rows


def markdown_quote(text: str) -> str:
    text = text.strip()
    if not text:
        return "> [No extracted passage text available]"
    return "\n".join(">" + (" " + line if line else "") for line in text.splitlines())


def format_citation(chunk: dict[str, Any]) -> str:
    citation = chunk.get("citation") or {}
    if not isinstance(citation, dict):
        return str(citation)

    display = citation.get("display")
    if display:
        return str(display)

    kind = citation.get("kind", "unknown")
    if kind == "pdf_page":
        start = citation.get("page_start", chunk.get("page_start"))
        end = citation.get("page_end", chunk.get("page_end"))
        if start is not None and end is not None:
            return f"pages {start}-{end}"
        return f"PDF page {start}" if start is not None else "PDF page unknown"

    start = citation.get("start_seconds", chunk.get("timestamp_start_seconds"))
    end = citation.get("end_seconds", chunk.get("timestamp_end_seconds"))
    if start is not None and end is not None:
        return f"{start:.3f}-{end:.3f} seconds"
    return "timestamp unknown"


def format_passage(
    chunk_id: str,
    chunk: dict[str, Any],
    number: int,
) -> list[str]:
    citation = format_citation(chunk)
    source_id = chunk.get("source_id", "unknown")
    review_status = chunk.get("review_status", "unknown")
    source_path = chunk.get("source_path", "unknown")
    source_sha256 = chunk.get("source_sha256", "not recorded")
    trust = chunk.get("trust", "not recorded")
    source_status = chunk.get("source_status", "not recorded")
    text = str(chunk.get("text", ""))

    lines = [
        f"### Candidate passage {number}: `{chunk_id}`",
        "",
        f"- **Source:** `{source_id}`",
        f"- **Citation:** {citation}",
        f"- **Current passage review status:** `{review_status}`",
        f"- **Trust field:** `{trust}`",
        f"- **Source content status:** `{source_status}`",
        f"- **Extracted source file:** `{source_path}`",
        f"- **Recorded source SHA-256:** `{source_sha256}`",
        f"- **Parent passage:** `{chunk.get('parent_id', 'unknown')}`",
        f"- **Extraction word count:** {chunk.get('word_count', 'unknown')}",
        "",
        "**Extracted passage text (review against the original source):**",
        "",
        markdown_quote(text),
        "",
        "**Reviewer assessment of this passage:**",
        "",
        "- [ ] Directly supports the question and its key points",
        "- [ ] Partially supports the question",
        "- [ ] Does not support the question",
        "- [ ] Extraction requires correction or further inspection",
        "- Reviewer notes:",
        "",
    ]
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export gold questions and their exact candidate passages for manual review."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Output Markdown path (defaults to eval/gold/review_v0.md).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing worksheet. Save any manual reviewer notes first.",
    )
    args = parser.parse_args()

    output_path = args.output
    if not output_path.is_absolute():
        output_path = ROOT / output_path

    if output_path.exists() and not args.overwrite:
        raise SystemExit(
            f"Review worksheet already exists: {output_path}. "
            "Preserve reviewer notes, or pass --overwrite intentionally."
        )

    questions = read_jsonl(QUESTIONS_PATH)
    chunks = read_jsonl(CHUNKS_PATH)

    chunk_map: dict[str, dict[str, Any]] = {}
    for chunk in chunks:
        chunk_id = str(chunk.get("chunk_id", ""))
        if not chunk_id or chunk_id in chunk_map:
            raise ValueError(f"Missing or duplicate child chunk ID: {chunk_id!r}")
        chunk_map[chunk_id] = chunk

    question_ids = [str(q.get("question_id", "")) for q in questions]
    if len(question_ids) != len(set(question_ids)) or not all(question_ids):
        raise ValueError("Gold set contains missing or duplicate question IDs.")

    if len(questions) != 30:
        raise ValueError(f"Expected 30 questions, found {len(questions)}.")

    lines = [
        "# AlgoLens — Gold Question Review Worksheet v0",
        "",
        "> **DRAFT ONLY — NOT A VERIFIED GOLD SET.** Use this worksheet to "
        "compare each question and proposed passage label with the original "
        "MIT lecture source. Automatic extraction and captions are not yet "
        "fully reviewed.",
        "",
        "## Review procedure",
        "",
        "1. Read the question and its key points.",
        "2. Open each cited page in the original typed-notes PDF or inspect the "
        "caption interval in the corresponding lecture video.",
        "3. Decide whether each passage directly supports the question. A "
        "retrieved passage is not automatically a valid gold label.",
        "4. Confirm the question is answerable from the in-scope lecture sources.",
        "5. Add reviewer notes and record the final label decision.",
        "6. Do not mark a label verified until the source and all necessary "
        "evidence passages have been checked.",
        "",
        "### Review legend",
        "",
        "- `Accept`: question, answerability, key points, and gold IDs are supported.",
        "- `Revise`: adjust the question, key points, or passage IDs.",
        "- `Unanswerable`: evidence is not in the current approved scope.",
        "- `Needs follow-up`: source or extraction requires additional inspection.",
        "",
        "The passages below are transcribed from the current extracted chunk "
        "corpus. They are not substitutes for checking the original PDF or video.",
        "",
        "## Review summary",
        "",
        f"- Draft questions: {len(questions)}",
        f"- Child passages available: {len(chunk_map)}",
        f"- Answerable labels proposed: {sum(q.get('answerable') is True for q in questions)}",
        f"- Unanswerable labels proposed: {sum(q.get('answerable') is False for q in questions)}",
        "- Overall review status: `draft_needs_human_review`",
        "",
        "---",
        "",
    ]

    referenced_ids: set[str] = set()
    passages_per_question: list[int] = []
    suspicious: dict[str, list[str]] = {}

    for question in questions:
        question_id = str(question["question_id"])
        question_text = str(question.get("question", ""))
        gold_ids = list(question.get("gold_passage_ids", []))
        passages_per_question.append(len(gold_ids))

        unknown = set(gold_ids) - set(chunk_map)
        if unknown:
            raise ValueError(f"{question_id} references missing passage IDs: {sorted(unknown)}")

        status = str(question.get("label_status", "missing"))
        answerable = question.get("answerable")
        answerability = "PROPOSED ANSWERABLE" if answerable else "PROPOSED UNANSWERABLE"

        lines.extend(
            [
                f"## {question_id} — {question.get('question_type', 'unknown')}",
                "",
                f"**Question:** {question_text}",
                "",
                f"- **Proposed classification:** {answerability}",
                f"- **Difficulty:** {question.get('difficulty', 'unknown')}",
                f"- **Current label status:** `{status}`",
                f"- **Proposed gold passage count:** {len(gold_ids)}",
                "",
                "**Key points / expected behavior to verify:**",
                "",
            ]
        )

        for point in question.get("key_points", []):
            lines.append(f"- {point}")

        if not question.get("key_points"):
            lines.append("- [No key points recorded]")

        lines.extend(
            [
                "",
                "**Proposed gold passage IDs:**",
                "",
            ]
        )

        if gold_ids:
            for chunk_id in gold_ids:
                lines.append(f"- `{chunk_id}`")
        else:
            lines.append("- None (intentionally empty for the proposed unanswerable label).")

        notes = str(question.get("annotation_notes", "")).strip()
        if notes:
            lines.extend(["", f"**Existing annotation caveat:** {notes}"])

        lines.extend(
            [
                "",
                "**Overall question-label decision:**",
                "",
                "- [ ] Accept as labeled",
                "- [ ] Revise question wording",
                "- [ ] Revise key points",
                "- [ ] Add, remove, or replace gold passage IDs",
                "- [ ] Reclassify as unanswerable",
                "- [ ] Needs follow-up on the original source",
                "- **Reviewer notes:**",
                "",
            ]
        )

        if gold_ids:
            for number, chunk_id in enumerate(gold_ids, start=1):
                chunk = chunk_map[chunk_id]
                referenced_ids.add(chunk_id)
                lines.extend(format_passage(chunk_id, chunk, number))

                for field in ("text", "retrieval_text"):
                    value = str(chunk.get(field, ""))
                    hits = [token for token in SUSPICIOUS_STRINGS if token in value]
                    if hits:
                        suspicious.setdefault(chunk_id, [])
                        suspicious[chunk_id].extend(hits)

        else:
            lines.extend(
                [
                    "### No gold passage is assigned",
                    "",
                    "Check that the question truly cannot be answered from the "
                    "current lecture scope. Search the actual source and corpus "
                    "before accepting the unanswerable label.",
                    "",
                    "- [ ] Confirmed out of scope",
                    "- [ ] Found supporting evidence; add its passage ID",
                    "- [ ] Question needs rewriting",
                    "- Reviewer notes:",
                    "",
                ]
            )

        lines.extend(["---", ""])

    lines.extend(
        [
            "## Dataset-level review",
            "",
            "Complete this after reviewing all question sections.",
            "",
            "- [ ] Every answerable question has sufficient supporting evidence.",
            "- [ ] No proposed gold passage is merely topically related without support.",
            "- [ ] Every multi-hop question has all required evidence passages.",
            "- [ ] Every unanswerable question has been checked against the in-scope sources.",
            "- [ ] Formula-based questions have been checked against the original PDF/video.",
            (
                "- [ ] Question wording does not reveal the answer in a way that "
                "makes retrieval artificially easy."
            ),
            (
                "- [ ] Review decisions and revisions have been transferred back "
                "into the canonical gold dataset."
            ),
            "",
            "### Final reviewer declaration",
            "",
            "- Reviewer:",
            "- Review date:",
            "- Questions accepted without changes:",
            "- Questions revised:",
            "- Questions reclassified as unanswerable:",
            "- Questions requiring further source inspection:",
            (
                "- Overall dataset status: `draft_needs_human_review` until all "
                "required checks are complete."
            ),
            "",
            "## Encoding diagnostic",
            "",
        ]
    )

    if suspicious:
        lines.extend(
            [
                "Common encoding-warning sequences were detected in the "
                "referenced extracted passages. Inspect the original source "
                "before accepting the affected labels.",
                "",
                "| Passage ID | Detected sequences |",
                "|---|---|",
            ]
        )
        for chunk_id, tokens in sorted(suspicious.items()):
            encoded_tokens = ", ".join(sorted(set(tokens)))
            lines.append(f"| `{chunk_id}` | `{encoded_tokens}` |")
        lines.append("")
    else:
        lines.extend(
            [
                "No common mojibake or replacement-character sequences were "
                "detected in the referenced extracted passage text. This "
                "does not establish that the extraction is otherwise accurate.",
                "",
            ]
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    question_type_counts = Counter(str(q.get("question_type", "unknown")) for q in questions)

    print("Review worksheet created successfully.")
    print(f"Output: {output_path}")
    print(f"Questions included: {len(questions)}")
    print(f"Unique passage IDs referenced: {len(referenced_ids)}")
    print(f"Passage reference occurrences: {sum(passages_per_question)}")
    print(f"Question types: {json.dumps(dict(question_type_counts), sort_keys=True)}")

    if suspicious:
        print(
            "UTF-8 text diagnostic: suspicious character sequences found "
            "in the decoded corpus. Inspect the listed passages in the review file."
        )
        for chunk_id, tokens in sorted(suspicious.items()):
            print(f"  {chunk_id}: {json.dumps(sorted(set(tokens)))}")
    else:
        print(
            "UTF-8 text diagnostic: no common mojibake/replacement sequences "
            "found in referenced extracted passages."
        )

    print("No gold labels, corpus chunks, or evaluation reports were modified.")


if __name__ == "__main__":
    main()
