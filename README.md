---
title: AlgoLens
emoji: 🔎
colorFrom: indigo
colorTo: blue
sdk: gradio
python_version: "3.12"
app_file: app/app.py
pinned: false
---

# AlgoLens

**A citation-first RAG tutor for MIT 6.046J Lecture 6.**

AlgoLens is designed to answer questions about Randomized Quicksort using approved
course material, trace claims to source passages, and abstain when the evidence
does not support a reliable answer.

## Current status — 26 October 2026

### Implemented

- Source manifest with source IDs, URLs, licences, source hashes, and integrity checks.
- Caption/VTT parsing into timestamped JSONL; page-aware PDF extraction and extraction experiments.
- Chunking, provenance/citation metadata, reviewed-candidate parsing, and eligibility checks.
- BM25 and dense retrieval, reciprocal-rank fusion (RRF), and cross-encoder reranking.
- Evidence-bound SQLite answer caching, answerability/abstention logic, structured answer contracts, an OpenAI-compatible provider,
  and a claim-grounding verification wrapper.
- A Gradio UI with Ask, Evidence, Trace, Evaluation, and About views.
- CLI commands for `status`, `ingest`, `index`, and `eval`.
- HTTP liveness and grounded-runtime readiness probes at /healthz and /readyz, with the Gradio UI mounted on the same server.
- Pytest, Ruff, mypy, and GitHub Actions CI configuration.

### Current source and corpus state

The pinned typed-notes PDF and English caption VTT passed SHA-256 verification in
the latest local ingestion run. The 1,458 caption cues are converted into a
timestamped transcript. The original raw PDF and VTT stay in the git-ignored
`corpus/raw/` directory; generated extraction artifacts are kept separately.

The printed pages 5–6 transcription has project-owner approval, and its two
parent/child chunks are integrated into the canonical reviewed-chunk files.
**They remain retrieval-disabled** until a separate retrieval-eligibility decision
is made. Page 3–4 Quicksort candidate material and its child chunks are
version-controlled, but project-owner review is still pending. An 80-question
evaluation candidate bank is also version-controlled in `eval/gold/questions_v1_candidate.jsonl` with a separate per-question review worksheet.

### Production readiness: intentionally blocked

At the current checkpoint, **zero canonical child passages meet all production
eligibility signals**. The app should start in safe mode and must not generate
answers from pending or retrieval-disabled content. The CLI production index
command is expected to block until the corpus is explicitly approved.

The final evaluation remains blocked. The active file `questions_v0.jsonl` still has 30 draft questions; a separate 80-question candidate bank exists but has not been promoted or reviewed. Its proposed 50-dev/30-test split is not frozen, and its gold passage IDs point to experimental chunks rather than approved canonical evidence. Existing retrieval reports are exploratory diagnostics—not final benchmark results. The candidate bank is intentionally not consumed by the CLI until a human-reviewed promotion is performed.

### Next acceptance gates

1. Complete owner review of source-grounded candidate passages without relaxing
   the eligibility checks to make the app answer.
2. Make a separate, explicit retrieval-eligibility decision and test the real
   approved-corpus path.
3. Review the separate 80-question candidate bank and each proposed source label; revise its IDs to map to canonical reviewed chunks, then freeze the development/test split before final evaluation.
4. Validate provider integration, review claim verification on human-labelled
   examples, calibrate thresholds only on development data, and evaluate once
   on held-out test questions.
5. Finish ablations, operational/health probes, and live deployment only after
   the local acceptance gates pass.

## Local development

Python 3.12 is required.

```powershell
uv sync --all-groups
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src
uv run pytest -q
```

Set `ALGOLENS_CACHE_PATH` to a writable SQLite file path to change the answer-cache location. The default cache lives in the operating system temporary directory; it is bounded to 256 entries with a seven-day TTL. Cache keys are SHA-256 hashes over the question, evidence, model/corpus namespace, and partial-answer mode; API keys and raw questions are not persisted. Cache hits still pass through the normal answer and claim-verification checks.

Optional provider failover can be enabled with `ALGOLENS_FALLBACK_PROVIDER=groq` or `ollama`, with optional `ALGOLENS_FALLBACK_MODEL`, `ALGOLENS_FALLBACK_BASE_URL`, `ALGOLENS_FALLBACK_API_KEY`, and `ALGOLENS_FALLBACK_TIMEOUT_SECONDS` settings. The fallback is attempted only after the primary provider fails or returns invalid citations. If every provider fails, AlgoLens returns approved source passages only; it does not release the failed draft.

Operational probes:

- GET /healthz returns 200 when the process is up.
- GET /readyz returns 200 only when canonical evidence and the grounded runtime are ready. It returns 503 in safe mode; this is intentional while the corpus has no eligible passages.

Useful CLI commands:

```powershell
uv run python -m algolens.cli status
uv run python -m algolens.cli ingest
uv run python -m algolens.cli index
uv run python -m algolens.cli eval
uv run python -m algolens.cli eval --diagnostic --retriever bm25
```

The production `index` and final `eval` commands intentionally stop when their
approval and evaluation prerequisites are not satisfied. Diagnostic evaluation
does not authorize answer generation.

## Licensing

See `CONTENT-LICENSE.md` and `docs/sources.md` for MIT OpenCourseWare
attribution and the project's third-party content-handling policy.
