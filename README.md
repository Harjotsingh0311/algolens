# AlgoLens

**A citation-first RAG tutor for MIT 6.046J Lecture 6.**

AlgoLens is being built to answer questions about Randomized Quicksort using
approved course material, trace answers to source passages, and abstain when
the available evidence is insufficient.

## Current status — 25 October 2026

### Implemented

- Python 3.12 development environment and reproducible dependency lockfile.
- Validated source manifest with source IDs, URLs, licences, and SHA-256 metadata.
- SHA-256 verification and safe temporary-file download logic.
- VTT caption auditing and timestamped JSONL transcript conversion.
- Page-aware PDF-to-Markdown extraction with unit tests.
- Pytest, Ruff, mypy, documentation, and GitHub Actions CI foundation.

### Source data verified locally

- YouTube caption track: 1,458 cues converted to `corpus/processed/transcript.jsonl`.
- Captions SHA-256: `3e6ce969b47c94fdfa7108eff91b2ec0029e5151b0b9f9a75b74f3df31beeed1`.
- Typed notes PDF SHA-256: `fac37c9721e67c2f5723536ae412bd200ae7580675bd0f53b21f2878af39bc55`.
- Both raw source files remain in the git-ignored `corpus/raw/` directory.

Hashes identify exact files, not their factual accuracy. Caption spot-checking and
review of the extracted mathematical content remain necessary.

### Not yet implemented or completed

- Actual extraction and manual formula review of the downloaded notes PDF.
- Final transcript/source alignment and teach-unit chunking.
- Dense embeddings, BM25 retrieval, RRF, and cross-encoder reranking.
- Abstention calibration, cited generation, and independent claim verification.
- Gradio application, evaluation runs, ablations, and live deployment.

No retrieval metrics, answer-quality scores, or live demo URL are claimed yet.

## Local development

Python 3.12 is required.

```powershell
uv sync --all-groups
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src
uv run pytest -q
```

## Licensing

See `CONTENT-LICENSE.md` and `docs/sources.md` for MIT OpenCourseWare attribution
and the project's third-party content handling policy.