"""Safely download the initial copy of the approved typed lecture notes."""

import hashlib
from pathlib import Path

import httpx

from algolens.ingest.manifest import load_manifest

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ID = "L06_TYPED_NOTES"
MAX_BYTES = 25 * 1024 * 1024


def main() -> None:
    manifest = load_manifest(ROOT / "corpus" / "manifest.yaml")
    matches = [
        source for source in manifest["sources"]
        if source["id"] == SOURCE_ID
    ]

    if len(matches) != 1:
        raise SystemExit(f"Expected exactly one source record for {SOURCE_ID}.")

    source = matches[0]

    if source.get("sha256") is not None:
        raise SystemExit(
            "This source already has a pinned hash. Use the verified downloader."
        )

    url = source.get("url")
    if not isinstance(url, str):
        raise SystemExit(f"{SOURCE_ID} has no valid URL.")

    parsed = httpx.URL(url)
    if parsed.scheme != "https" or parsed.host not in {
        "ocw.mit.edu",
        "www.ocw.mit.edu",
        "live.ocw.mit.edu",
    }:
        raise SystemExit(f"Refusing unexpected source host: {parsed.host}")

    destination = ROOT / "corpus" / "raw" / "L06_TYPED_NOTES.pdf"
    temporary = destination.with_name(destination.name + ".part")

    if destination.exists():
        raise SystemExit(
            f"Destination already exists: {destination}. Inspect it first."
        )

    digest = hashlib.sha256()
    total_bytes = 0
    prefix = bytearray()
    final_url = url
    content_type = "unknown"

    try:
        destination.parent.mkdir(parents=True, exist_ok=True)

        with httpx.Client(
            timeout=60.0,
            follow_redirects=True,
        ) as client:
            with client.stream("GET", url) as response:
                response.raise_for_status()
                final_url = str(response.url)
                content_type = response.headers.get(
                    "content-type", "unknown"
                )

                final_host = response.url.host
                if final_host not in {
                    "ocw.mit.edu",
                    "www.ocw.mit.edu",
                    "live.ocw.mit.edu",
                }:
                    raise RuntimeError(
                        f"Unexpected final host after redirect: {final_host}"
                    )

                declared_size = response.headers.get("content-length")
                if declared_size and int(declared_size) > MAX_BYTES:
                    raise RuntimeError(
                        f"Response exceeds the {MAX_BYTES:,}-byte size limit."
                    )

                with temporary.open("wb") as output:
                    for chunk in response.iter_bytes(64 * 1024):
                        if not chunk:
                            continue

                        total_bytes += len(chunk)
                        if total_bytes > MAX_BYTES:
                            raise RuntimeError(
                                f"Download exceeded {MAX_BYTES:,} bytes."
                            )

                        if len(prefix) < 5:
                            prefix.extend(chunk[: 5 - len(prefix)])

                        digest.update(chunk)
                        output.write(chunk)

        if bytes(prefix) != b"%PDF-":
            raise RuntimeError(
                "Downloaded content does not have a PDF signature."
            )

        if total_bytes == 0:
            raise RuntimeError("Downloaded file is empty.")

        temporary.replace(destination)

    except Exception:
        temporary.unlink(missing_ok=True)
        raise

    print("========== INITIAL PDF DOWNLOAD ==========")
    print(f"Source ID: {SOURCE_ID}")
    print(f"Final URL: {final_url}")
    print(f"Content-Type: {content_type}")
    print(f"File: {destination}")
    print(f"Size: {total_bytes:,} bytes")
    print(f"SHA-256: {digest.hexdigest()}")
    print("PDF signature: verified")
    print("Status: downloaded; semantic review and manifest pinning pending")


if __name__ == "__main__":
    main()