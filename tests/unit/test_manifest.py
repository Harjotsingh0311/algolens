from pathlib import Path

import pytest
import yaml

from algolens.ingest.manifest import ManifestError, load_manifest

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_current_manifest_loads() -> None:
    manifest = load_manifest(PROJECT_ROOT / "corpus" / "manifest.yaml")

    assert manifest["version"] == "0.1.0"

    sources = manifest["sources"]
    assert isinstance(sources, list)
    assert len(sources) == 5
    assert "L06_YOUTUBE_CAPTIONS" in {source["id"] for source in sources}

    source_ids = [source["id"] for source in sources]
    assert len(source_ids) == len(set(source_ids))


def test_missing_url_is_rejected_with_source_id(
    tmp_path: Path,
) -> None:
    manifest = {
        "version": "0.1.0",
        "corpus_id": "test-corpus",
        "sources": [
            {
                "id": "L06_MISSING_URL",
                "lecture": 6,
                "type": "video",
                "url": "",
                "licence": "CC BY-NC-SA 4.0",
                "sha256": None,
                "tier": 1,
                "trust": "primary",
                "scope": "randomized_quicksort",
                "status": "pending_download",
            }
        ],
    }

    path = tmp_path / "manifest.yaml"
    path.write_text(
        yaml.safe_dump(manifest),
        encoding="utf-8",
    )

    with pytest.raises(ManifestError, match="L06_MISSING_URL.*URL"):
        load_manifest(path)


def test_duplicate_source_ids_are_rejected(
    tmp_path: Path,
) -> None:
    source = {
        "id": "L06_DUPLICATE",
        "lecture": 6,
        "type": "video",
        "url": "https://example.com/video.mp4",
        "licence": "CC BY-NC-SA 4.0",
        "sha256": None,
        "tier": 1,
        "trust": "primary",
        "scope": "randomized_quicksort",
        "status": "pending_download",
    }

    manifest = {
        "version": "0.1.0",
        "corpus_id": "test-corpus",
        "sources": [source, source.copy()],
    }

    path = tmp_path / "manifest.yaml"
    path.write_text(
        yaml.safe_dump(manifest),
        encoding="utf-8",
    )

    with pytest.raises(ManifestError, match="L06_DUPLICATE"):
        load_manifest(path)


def test_malformed_sha256_is_rejected(
    tmp_path: Path,
) -> None:
    source = {
        "id": "L06_BAD_HASH",
        "lecture": 6,
        "type": "video",
        "url": "https://example.com/video.mp4",
        "licence": "CC BY-NC-SA 4.0",
        "sha256": "not-a-valid-hash",
        "tier": 1,
        "trust": "primary",
        "scope": "randomized_quicksort",
        "status": "pending_download",
    }

    manifest = {
        "version": "0.1.0",
        "corpus_id": "test-corpus",
        "sources": [source],
    }

    path = tmp_path / "manifest.yaml"
    path.write_text(
        yaml.safe_dump(manifest),
        encoding="utf-8",
    )

    with pytest.raises(ManifestError, match="L06_BAD_HASH.*SHA-256"):
        load_manifest(path)
