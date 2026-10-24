import hashlib
from pathlib import Path

import httpx
import pytest

from algolens.ingest.fetch import (
    HashMismatchError,
    ManifestError,
    download_source,
    verify_file_hash,
)


def test_t12_hash_mismatch_identifies_source_and_file(
    tmp_path: Path,
) -> None:
    source_file = tmp_path / "lecture_notes.pdf"
    source_file.write_bytes(b"actual lecture content")

    wrong_hash = "0" * 64

    with pytest.raises(HashMismatchError) as error:
        verify_file_hash(
            source_file,
            expected_sha256=wrong_hash,
            source_id="L06_TYPED_NOTES",
        )

    message = str(error.value)
    assert "L06_TYPED_NOTES" in message
    assert str(source_file) in message


def test_t13_missing_url_fails_without_creating_output(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "raw" / "transcript.pdf"

    source = {
        "id": "L06_TRANSCRIPT",
        "url": " ",
        "sha256": "a" * 64,
    }

    with pytest.raises(ManifestError, match="L06_TRANSCRIPT.*URL"):
        download_source(source, destination)

    assert not destination.exists()
    assert not destination.parent.exists()


def test_hash_mismatch_does_not_publish_download(
    tmp_path: Path,
) -> None:
    payload = b"actual file content"
    expected_hash = hashlib.sha256(b"expected file content").hexdigest()

    source = {
        "id": "L06_TYPED_NOTES",
        "url": "https://example.invalid/lecture_notes.pdf",
        "sha256": expected_hash,
    }

    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=payload))

    destination = tmp_path / "raw" / "lecture_notes.pdf"

    with httpx.Client(transport=transport) as client:
        with pytest.raises(HashMismatchError, match="L06_TYPED_NOTES"):
            download_source(source, destination, client=client)

    assert not destination.exists()
    assert not list(tmp_path.rglob("*.part"))
