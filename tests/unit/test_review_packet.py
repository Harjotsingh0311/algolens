from __future__ import annotations

import json
from pathlib import Path

from algolens.evaluation.review_packet import build_review_packet, main


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_review_packet_shows_diagnostic_warning_and_does_not_mutate_inputs(
    tmp_path: Path,
) -> None:
    question = {
        "question_id": "GQ001",
        "question": "What does the pivot do?",
        "question_type": "definition_recall",
        "split": "dev",
        "answerable": True,
        "label_status": "draft_needs_human_review",
        "key_points": ["It partitions the array."],
        "gold_passage_ids": ["diagnostic-child-1"],
        "annotation_notes": "",
    }
    diagnostic_chunk = {
        "chunk_id": "diagnostic-child-1",
        "source_id": "L06_YOUTUBE_CAPTIONS",
        "citation": {"display": "00:01:02–00:01:20"},
        "text": "The pivot divides elements into partition regions.",
    }
    write_jsonl(tmp_path / "eval/gold/questions_v1_candidate.jsonl", [question])
    write_jsonl(
        tmp_path / "corpus/experiments/chunking/children.jsonl",
        [diagnostic_chunk],
    )
    write_jsonl(
        tmp_path / "corpus/processed/reviewed_chunks/children.jsonl",
        [],
    )

    packet = build_review_packet(tmp_path)

    assert "diagnostic-only; NOT approved canonical evidence" in packet
    assert "The pivot divides elements into partition regions." in packet
    assert "Final evaluation authorized: **No**" in packet
    assert "Ready for a separate approval review" in packet
    assert "Automated wording/type flags (advisory)" in packet
    assert "Prioritized review queue: **1** questions" in packet
    assert "Review priority: P0" in packet
    assert "Review reasons: diagnostic_only_passage_ids, human_review_pending" in packet
    assert "None triggered" in packet
    assert (
        json.loads(
            (tmp_path / "eval/gold/questions_v1_candidate.jsonl").read_text(encoding="utf-8")
        )
        == question
    )


def test_review_packet_flags_empty_passage_list_for_human_check(tmp_path: Path) -> None:
    question = {
        "question_id": "GQ080",
        "question": "Is this outside the lecture?",
        "question_type": "unanswerable_out_of_corpus",
        "split": "test",
        "answerable": False,
        "label_status": "draft_needs_human_review",
        "key_points": ["The requested topic is not covered by the lecture."],
        "gold_passage_ids": [],
        "annotation_notes": "",
    }
    write_jsonl(tmp_path / "eval/gold/questions_v1_candidate.jsonl", [question])
    write_jsonl(tmp_path / "corpus/experiments/chunking/children.jsonl", [])
    write_jsonl(tmp_path / "corpus/processed/reviewed_chunks/children.jsonl", [])

    packet = build_review_packet(tmp_path)

    assert "No passage IDs supplied." in packet
    assert "Confirm that this is intentional for an unanswerable question" in packet


def test_review_packet_cli_preserves_existing_output_by_default(tmp_path: Path, capsys) -> None:
    output = tmp_path / "existing-review-packet.md"
    original = "Do not overwrite this review work.\\n"
    output.write_text(original, encoding="utf-8")

    try:
        main(["--root", str(tmp_path), "--output", str(output)])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("Expected existing output to be preserved by default")

    assert output.read_text(encoding="utf-8") == original
    assert "already exists" in capsys.readouterr().err
