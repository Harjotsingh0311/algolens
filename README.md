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
- Pytest, Ruff, mypy, and GitHub Actions CI configuration.

### Current source and corpus state

The pinned typed-notes PDF and English caption VTT passed SHA-256 verification in
the latest local ingestion run. The 1,458 caption cues are converted into a
timestamped transcript. The original raw PDF and VTT stay in the git-ignored
`corpus/raw/` directory; generated extraction artifacts are kept separately.

The printed pages 5–6 transcription has project-owner approval, and its two
parent/child chunks are integrated into the canonical reviewed-chunk files.
**They remain retrieval-disabled** until a separate retrieval-eligibility decision
is made. A page 3–4 Quicksort candidate summary and three child chunks are
version-controlled, but project-owner review is still pending.

### Production readiness: intentionally blocked

At the current checkpoint, **zero canonical child passages meet all production
eligibility signals**. The app should start in safe mode and must not generate
answers from pending or retrieval-disabled content. The CLI production index
command is expected to block until the corpus is explicitly approved.

The final evaluation is also blocked: there are 30 draft questions rather than
the required 80, labels still need human review, the 50-dev/30-test split is not
finalized, and some gold passage IDs do not match an approved corpus. Existing
retrieval reports are exploratory diagnostics—not final benchmark results.

### Next acceptance gates

1. Complete owner review of source-grounded candidate passages without relaxing
   the eligibility checks to make the app answer.
2. Make a separate, explicit retrieval-eligibility decision and test the real
   approved-corpus path.
3. Review all gold labels, establish the 50-development/30-test split, and add
   the remaining questions before final evaluation.
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

Set `ALGOLENS_CACHE_PATH` to a writable SQLite file path to change the answer-cache location. The default cache lives in the operating system temporary directory; it is bounded to 256 entries with a seven-day TTL. Cache keys are SHA-256 hashes over the question, evidence, model/corpus namespace, and partial-answer mode; API keys and raw questions are not persisted. Cache hits still pass through the normal answer and claim-verification checks.\n\nUseful CLI commands:

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
