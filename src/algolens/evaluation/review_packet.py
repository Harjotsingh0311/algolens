from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(f"Required JSONL file does not exist: {path}")
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in {path}, line {line_number}.") from exc
            if not isinstance(row, dict):
                raise ValueError(f"Expected a JSON object in {path}, line {line_number}.")
            rows.append(row)
    return rows


def _safe_text(value: Any) -> str:
    return value if isinstance(value, str) else ""


def build_review_packet(root: Path) -> str:
    """Build a human-review Markdown packet without changing gold data or approvals."""
    questions_path = root / "eval" / "gold" / "questions_v1_candidate.jsonl"
    diagnostic_path = root / "corpus" / "experiments" / "chunking" / "children.jsonl"
    canonical_path = root / "corpus" / "processed" / "reviewed_chunks" / "children.jsonl"

    questions = read_jsonl(questions_path)
    diagnostic = read_jsonl(diagnostic_path)
    canonical = read_jsonl(canonical_path)
    diagnostic_by_id = {
        row["chunk_id"]: row
        for row in diagnostic
        if isinstance(row.get("chunk_id"), str)
    }
    canonical_ids = {
        row["chunk_id"]
        for row in canonical
        if isinstance(row.get("chunk_id"), str)
    }

    lines = [
        "# Gold-question human review packet",
        "",
        "> Review aid only. This file does not approve questions, labels, passages, or retrieval eligibility.",
        (
            "> Treat diagnostic chunk text as a proposed evidence lead, "
            "not as approved canonical evidence."
        ),
        "",
        "## Reviewer instructions",
        "",
        "- Check the original lecture source for every question and each key point.",
        "- Confirm whether the question is answerable from the approved lecture corpus.",
        "- For answerable questions, record only passage IDs that directly support the answer.",
        (
            "- For unanswerable questions, confirm the reason and keep gold "
            "passage IDs empty when appropriate."
        ),
        "- Do not change corpus approval flags through this packet.",
        (
            "- Record the reviewer and decision in the review record before "
            "any separate approval workflow."
        ),
        "",
        f"Candidate question count: **{len(questions)}**",
        "",
    ]

    for question in questions:
        qid = _safe_text(question.get("question_id")) or "<missing question_id>"
        qtext = _safe_text(question.get("question")) or "<missing question text>"
        gold_ids = question.get("gold_passage_ids")
        if not isinstance(gold_ids, list):
            gold_ids = []
        gold_ids = [value for value in gold_ids if isinstance(value, str)]
        answerable = question.get("answerable")
        split = _safe_text(question.get("split")) or "unspecified"
        qtype = _safe_text(question.get("question_type")) or "unspecified"

        lines.extend(
            [
                f"## {qid} — {qtype}",
                "",
                f"- **Split:** {split}",
                f"- **Answerable (candidate label):** {answerable}",
                f"- **Label status:** {_safe_text(question.get('label_status')) or 'missing'}",
                f"- **Question:** {qtext}",
                "",
                "### Candidate key points",
                "",
            ]
        )
        key_points = question.get("key_points")
        if isinstance(key_points, list) and key_points:
            lines.extend(f"- {point}" for point in key_points)
        else:
            lines.append("- [ ] Missing key points — review required.")

        lines.extend(["", "### Proposed passage references", ""])
        if not gold_ids:
            lines.append(
                "- No passage IDs supplied. Confirm that this is intentional for an unanswerable "
                "question; otherwise locate supporting evidence."
            )
        else:
            for chunk_id in gold_ids:
                if chunk_id in canonical_ids:
                    status = "present in canonical corpus; still requires human label review"
                elif chunk_id in diagnostic_by_id:
                    status = "diagnostic-only; NOT approved canonical evidence"
                else:
                    status = "not found in either inspected corpus"
                lines.extend([f"#### `{chunk_id}`", "", f"**Mapping status:** {status}", ""])
                chunk = diagnostic_by_id.get(chunk_id)
                if chunk is None:
                    lines.append("No diagnostic text available for this ID.")
                else:
                    citation = chunk.get("citation")
                    display = citation.get("display") if isinstance(citation, dict) else None
                    lines.append(
                        f"**Source:** {_safe_text(chunk.get('source_id'))}; "
                        f"**location:** {display or 'citation missing'}"
                    )
                    lines.append("")
                    text = _safe_text(chunk.get("text")) or _safe_text(
                        chunk.get("retrieval_text")
                    )
                    lines.extend(
                        ["> " + part for part in text.splitlines()]
                        if text
                        else ["> No text found."]
                    )
                lines.append("")

        annotation_notes = _safe_text(question.get("annotation_notes")).strip()
        if annotation_notes:
            lines.extend(["### Existing annotation notes", "", annotation_notes, ""])
        lines.extend(
            [
                "### Human review decision",
                "",
                "- [ ] Question wording checked against source",
                "- [ ] Answerability label checked",
                "- [ ] Every key point checked against source",
                "- [ ] Passage IDs checked against canonical evidence",
                "- [ ] Citation location checked",
                "- [ ] Ready for a separate approval review",
                "",
                "Reviewer: ____________________",
                "",
                "Decision / corrections: ______________________________________________",
                "",
                "---",
                "",
            ]
        )

    lines.extend(
        [
            "## Safety status",
            "",
            "- Candidate question file changed: **No**",
            "- Canonical chunks changed: **No**",
            "- Approval flags changed: **No**",
            "- Final evaluation authorized: **No**",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a human-review packet from candidate questions and diagnostic passages."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[3],
        help="AlgoLens repository root (defaults to the current source checkout).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional output path. Defaults to eval/results/gold_review_packet.md.",
    )
    args = parser.parse_args()
    root = args.root.resolve()
    output = args.output or root / "eval" / "results" / "gold_review_packet.md"
    if not output.is_absolute():
        output = root / output
    packet = build_review_packet(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(packet, encoding="utf-8")
    print(f"Review packet written: {output}")
    print("Read-only with respect to candidate questions, canonical chunks, and approval flags.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
