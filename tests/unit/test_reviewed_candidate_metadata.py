from __future__ import annotations

import pytest

from algolens.ingest.reviewed_candidate import validate_candidate_metadata

SOURCE_HASH = "a" * 64
CANDIDATE_HASH = "b" * 64


def valid_metadata() -> dict[str, object]:
    return {
        "source_sha256": SOURCE_HASH,
        "candidate_markdown_sha256": CANDIDATE_HASH,
        "project_owner_approval": "approved",
        "retrieval_eligible": False,
        "replaces_original_extraction": False,
    }


def test_approved_transcription_can_remain_retrieval_disabled() -> None:
    validate_candidate_metadata(
        valid_metadata(),
        actual_source_sha256=SOURCE_HASH,
        actual_candidate_sha256=CANDIDATE_HASH,
    )


def test_rejects_original_source_hash_mismatch() -> None:
    with pytest.raises(ValueError, match="source.*SHA-256"):
        validate_candidate_metadata(
            valid_metadata(),
            actual_source_sha256="c" * 64,
            actual_candidate_sha256=CANDIDATE_HASH,
        )


def test_rejects_candidate_hash_mismatch() -> None:
    with pytest.raises(ValueError, match="candidate.*SHA-256"):
        validate_candidate_metadata(
            valid_metadata(),
            actual_source_sha256=SOURCE_HASH,
            actual_candidate_sha256="d" * 64,
        )


def test_rejects_retrieval_enabled() -> None:
    metadata = valid_metadata()
    metadata["retrieval_eligible"] = True

    with pytest.raises(ValueError, match="retrieval"):
        validate_candidate_metadata(
            metadata,
            actual_source_sha256=SOURCE_HASH,
            actual_candidate_sha256=CANDIDATE_HASH,
        )


def test_rejects_pending_transcription_approval() -> None:
    metadata = valid_metadata()
    metadata["project_owner_approval"] = "pending"

    with pytest.raises(ValueError, match="approval"):
        validate_candidate_metadata(
            metadata,
            actual_source_sha256=SOURCE_HASH,
            actual_candidate_sha256=CANDIDATE_HASH,
        )


def test_rejects_original_extraction_replacement() -> None:
    metadata = valid_metadata()
    metadata["replaces_original_extraction"] = True

    with pytest.raises(ValueError, match="original extraction"):
        validate_candidate_metadata(
            metadata,
            actual_source_sha256=SOURCE_HASH,
            actual_candidate_sha256=CANDIDATE_HASH,
        )
