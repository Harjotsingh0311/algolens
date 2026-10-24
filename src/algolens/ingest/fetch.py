"""Download approved sources and verify their SHA-256 fingerprints."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from pathlib import Path

import httpx

_SHA256_PATTERN = re.compile(r"[0-9a-fA-F]{64}")


class ManifestError(ValueError):
    """Raised when source metadata is invalid."""


class HashMismatchError(ValueError):
    """Raised when a file does not match its declared SHA-256 hash."""


class SourceDownloadError(RuntimeError):
    """Raised when fetching or writing a source fails."""


def _source_id(source: Mapping[str, object]) -> str:
    """Return a validated source ID."""
    value = source.get("id")
    if not isinstance(value, str) or not value.strip():
        raise ManifestError("Source is missing a valid ID.")
    return value.strip()


def _expected_hash(source_id: str, value: object) -> str:
    """Validate and normalize an expected SHA-256 hash."""
    if not isinstance(value, str):
        raise ManifestError(f"Source '{source_id}' is missing a valid 64-character SHA-256 hash.")

    expected = value.strip()
    if _SHA256_PATTERN.fullmatch(expected) is None:
        raise ManifestError(f"Source '{source_id}' is missing a valid 64-character SHA-256 hash.")

    return expected.lower()


def _file_sha256(path: Path) -> str:
    """Calculate a file's SHA-256 hash without loading it all into memory."""
    digest = hashlib.sha256()

    with path.open("rb") as file:
        while chunk := file.read(1024 * 1024):
            digest.update(chunk)

    return digest.hexdigest()


def verify_file_hash(
    path: str | Path,
    expected_sha256: str,
    source_id: str,
) -> str:
    """Verify a file against its expected SHA-256 hash and return the actual hash."""
    file_path = Path(path)
    expected = _expected_hash(source_id, expected_sha256)
    actual = _file_sha256(file_path)

    if actual != expected:
        raise HashMismatchError(
            f"SHA-256 mismatch for source '{source_id}' at '{file_path}': "
            f"expected {expected}, got {actual}."
        )

    return actual


def download_source(
    source: Mapping[str, object],
    destination: str | Path,
    client: httpx.Client | None = None,
) -> Path:
    """Download a source, verify it, and atomically publish the verified file.

    The source mapping must contain `id`, `url`, and a pinned `sha256`.
    A missing or unverified fingerprint is never silently accepted.
    """
    source_id = _source_id(source)

    raw_url = source.get("url")
    if not isinstance(raw_url, str) or not raw_url.strip():
        raise ManifestError(f"Source '{source_id}' is missing a valid URL.")

    url = raw_url.strip()
    try:
        parsed_url = httpx.URL(url)
    except (TypeError, ValueError) as exc:
        raise ManifestError(f"Source '{source_id}' has an invalid URL.") from exc

    if parsed_url.scheme not in {"http", "https"} or not parsed_url.host:
        raise ManifestError(f"Source '{source_id}' must use a valid HTTP or HTTPS URL.")

    expected = _expected_hash(source_id, source.get("sha256"))
    destination_path = Path(destination)
    temporary_path = destination_path.with_name(destination_path.name + ".part")

    owns_client = client is None
    active_client = client if client is not None else httpx.Client(timeout=60.0)

    try:
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256()

        with active_client.stream(
            "GET",
            url,
            follow_redirects=True,
        ) as response:
            response.raise_for_status()

            with temporary_path.open("wb") as output:
                for chunk in response.iter_bytes(chunk_size=1024 * 1024):
                    output.write(chunk)
                    digest.update(chunk)

        actual = digest.hexdigest()
        if actual != expected:
            raise HashMismatchError(
                f"SHA-256 mismatch for source '{source_id}' at "
                f"'{destination_path}': expected {expected}, got {actual}."
            )

        temporary_path.replace(destination_path)
        return destination_path

    except httpx.HTTPError as exc:
        raise SourceDownloadError(f"Failed to download source '{source_id}': {exc}") from exc
    except OSError as exc:
        raise SourceDownloadError(f"Failed to write source '{source_id}': {exc}") from exc
    finally:
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError:
            pass

        if owns_client:
            active_client.close()
