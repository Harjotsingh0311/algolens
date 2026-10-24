# AlgoLens

**A citation-first, evidence-grounded RAG tutor for MIT 6.046J.**

AlgoLens is designed to answer questions about Randomized Quicksort using the
lecture corpus, trace every answer to supporting passages, and abstain when
the available evidence is insufficient.

## Current status

Phase 0: repository foundation.

The ingestion pipeline, search index, answer generation, application, and
deployment have not yet been completed. Evaluation numbers and deployment
URLs will be added only after they have been measured or verified.

## Planned capabilities

- Source manifests and SHA-256 integrity checks.
- Timestamped transcript passages and page-aware lecture notes.
- Parent-child teaching chunks and contextual headers.
- Hybrid BM25 and dense retrieval, merged with reciprocal rank fusion.
- Cross-encoder reranking.
- Evidence-aware abstention.
- Sentence-level citations and claim-level verification.
- Groq/Ollama provider adapter and response caching.
- Gradio interface, evaluation report, and automated CI.

## Local setup

Python 3.12 is required.

```powershell
uv sync --all-groups
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src
uv run pytest -q
```

## Data and licensing

Raw MIT lecture files belong in the git-ignored `corpus/raw/` directory.
Processed course material must retain the required attribution and applicable
Creative Commons terms. See `CONTENT-LICENSE.md` and `docs/sources.md`.

## Documentation

- `docs/concept.md` — project goals and rules.
- `docs/contract.md` — interfaces and data models.
- `docs/tests.md` — acceptance-test catalogue.
- `docs/architecture.md` — system architecture.
- `docs/refinement.md` — measured changes and results.