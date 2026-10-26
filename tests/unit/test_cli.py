from __future__ import annotations

import json
from pathlib import Path

import pytest

from algolens.cli import (
    build_parser,
    production_eligible,
    read_jsonl,
    sha256_file,
    write_json_atomic,
)


def test_production_eligibility_requires_all_signals() -> None:
    chunk = {
        "review_status": "approved",
        "eligible_for_answer": True,
        "retrieval_eligible": True,
    }
    assert production_eligible(chunk)

    assert not production_eligible({**chunk, "retrieval_eligible": False})
    assert not production_eligible({**chunk, "eligible_for_answer": False})
    assert not production_eligible({**chunk, "review_status": "candidate_review_pending"})
    assert not production_eligible({"review_status": "approved"})


def test_read_jsonl_reads_records(tmp_path: Path) -> None:
    path = tmp_path / "records.jsonl"
    path.write_text(
        '{"id":"one"}\n\n{"id":"two"}\n',
        encoding="utf-8",
    )
    assert read_jsonl(path) == [{"id": "one"}, {"id": "two"}]


def test_read_jsonl_rejects_malformed_json(tmp_path: Path) -> None:
    path = tmp_path / "bad.jsonl"
    path.write_text('{"id":"one"}\n{not-json}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="line 2"):
        read_jsonl(path)


def test_read_jsonl_rejects_non_object_rows(tmp_path: Path) -> None:
    path = tmp_path / "bad.jsonl"
    path.write_text("[1, 2, 3]\n", encoding="utf-8")
    with pytest.raises(ValueError, match="JSON object"):
        read_jsonl(path)


def test_sha256_file_is_stable(tmp_path: Path) -> None:
    path = tmp_path / "source.txt"
    path.write_bytes(b"algolens")
    digest = sha256_file(path)
    assert len(digest) == 64
    assert all(character in "0123456789abcdef" for character in digest)


def test_atomic_json_writer_creates_valid_json(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "report.json"
    write_json_atomic(path, {"status": "ok", "count": 3})
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "status": "ok",
        "count": 3,
    }
    assert not list(path.parent.glob("*.tmp"))


def test_parser_exposes_expected_commands() -> None:
    parser = build_parser()
    for command in ("status", "ingest", "review-check", "index", "eval"):
        args = parser.parse_args([command])
        assert args.command == command



def test_review_check_fails_closed_when_review_metadata_is_missing(
    tmp_path: Path,
) -> None:
    from algolens.cli import run_reviewed_candidate_check

    with pytest.raises(FileNotFoundError, match="Reviewed-candidate metadata is missing"):
        run_reviewed_candidate_check(tmp_path)


def test_review_check_never_changes_approval_when_metadata_is_missing(
    tmp_path: Path,
) -> None:
    from algolens.cli import run_reviewed_candidate_check

    with pytest.raises(FileNotFoundError):
        run_reviewed_candidate_check(tmp_path)

    assert not (tmp_path / "corpus" / "processed" / "reviewed_chunks").exists()
