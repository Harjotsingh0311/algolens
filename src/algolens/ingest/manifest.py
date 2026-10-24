"""Load and validate the AlgoLens source manifest."""

from __future__ import annotations

import re
from pathlib import Path
from typing import cast
from urllib.parse import urlsplit

import yaml

_SHA256_PATTERN = re.compile(r"[0-9a-fA-F]{64}")


class ManifestError(ValueError):
    """Raised when the corpus manifest is invalid."""


def _required_string(
    value: object,
    field: str,
    context: str,
) -> str:
    """Return a non-empty string or raise a descriptive manifest error."""
    if not isinstance(value, str) or not value.strip():
        raise ManifestError(f"{context}: field '{field}' must be a non-empty string.")
    return value.strip()


def load_manifest(path: str | Path) -> dict[str, object]:
    """Load and validate a YAML corpus manifest.

    An SHA-256 value of null is allowed for planning entries, but it does
    not mean the source is verified. Downloads must use a pinned 64-character
    SHA-256 fingerprint.
    """
    manifest_path = Path(path)

    try:
        text = manifest_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ManifestError(f"Cannot read manifest '{manifest_path}': {exc}") from exc

    try:
        parsed: object = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ManifestError(f"Invalid YAML in manifest '{manifest_path}': {exc}") from exc

    if not isinstance(parsed, dict):
        raise ManifestError("Manifest root must be a YAML mapping.")

    manifest = cast(dict[str, object], parsed)

    _required_string(manifest.get("version"), "version", "Manifest")
    _required_string(manifest.get("corpus_id"), "corpus_id", "Manifest")

    sources_raw = manifest.get("sources")
    if not isinstance(sources_raw, list) or not sources_raw:
        raise ManifestError("Manifest field 'sources' must be a non-empty list.")

    validated_sources: list[dict[str, object]] = []
    seen_ids: set[str] = set()

    for position, raw_source in enumerate(sources_raw, start=1):
        context = f"Source entry #{position}"

        if not isinstance(raw_source, dict):
            raise ManifestError(f"{context} must be a mapping.")

        source = cast(dict[str, object], raw_source)
        source_id = _required_string(source.get("id"), "id", context)

        if source_id in seen_ids:
            raise ManifestError(f"Duplicate source ID '{source_id}'.")

        seen_ids.add(source_id)

        url = _required_string(source.get("url"), "URL", f"Source '{source_id}'")

        try:
            parsed_url = urlsplit(url)
            valid_url = parsed_url.scheme in {"http", "https"} and bool(parsed_url.hostname)
        except ValueError:
            valid_url = False

        if not valid_url:
            raise ManifestError(f"Source '{source_id}' has an invalid HTTP or HTTPS URL.")

        _required_string(
            source.get("licence"),
            "licence",
            f"Source '{source_id}'",
        )

        expected_hash = source.get("sha256")

        if expected_hash is not None:
            if (
                not isinstance(expected_hash, str)
                or _SHA256_PATTERN.fullmatch(expected_hash.strip()) is None
            ):
                raise ManifestError(
                    f"Source '{source_id}' has an invalid SHA-256 hash; "
                    "expected 64 hexadecimal characters or null."
                )

            source["sha256"] = expected_hash.strip().lower()

        validated_sources.append(source)

    manifest["sources"] = validated_sources
    return manifest
