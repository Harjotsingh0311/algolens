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

**A citation-first RAG tutor for MIT 6.046J — Lecture 6: Randomization, Matrix Multiply, and Quicksort.**

AlgoLens is a research prototype that answers lecture questions from explicitly approved course evidence, shows the passages behind an answer, and abstains when evidence is missing or a claim cannot be verified. It is designed around **evidence quality and traceability—not answer generation at any cost**.

<p align="left">
  <a href="https://github.com/Harjotsingh0311/algolens/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/Harjotsingh0311/algolens/actions/workflows/ci.yml/badge.svg"></a>
  <img alt="Python 3.12" src="https://img.shields.io/badge/python-3.12-3776AB?logo=python&logoColor=white">
  <img alt="Gradio" src="https://img.shields.io/badge/UI-Gradio-F97316">
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/Code%20license-MIT-green.svg"></a>
  <img alt="Status: research prototype" src="https://img.shields.io/badge/status-research%20prototype-orange">
</p>

> **Current status (26 October 2026): safe mode is intentional.** The application and core retrieval/answering components are implemented, but no canonical child passage currently satisfies every production approval signal. AlgoLens must not generate an answer from pending, experimental, or retrieval-disabled material.

## Contents

- [What it does](#what-it-does)
- [Architecture](#architecture)
- [Implementation and limitations](#implementation-and-limitations)
- [Source material](#source-material)
- [Quick start](#quick-start)
- [Configuration](#configuration)
- [Commands](#commands)
- [Corpus approval and safe mode](#corpus-approval-and-safe-mode)
- [Evaluation status](#evaluation-status)
- [Repository layout](#repository-layout)
- [Quality checks](#quality-checks)
- [Licensing and attribution](#licensing-and-attribution)
- [Roadmap](#roadmap)

## What it does

- **Lecture-scoped answers:** targets MIT 6.046J Spring 2015, Lecture 6.
- **Source-aware ingestion:** validates a source manifest and source hashes; converts VTT captions into timestamped JSONL and extracts PDFs into page-aware Markdown.
- **Provenance-preserving chunks:** keeps source IDs and page/timestamp citation metadata with extracted passages.
- **Hybrid retrieval:** BM25 lexical retrieval and dense retrieval, combined with reciprocal-rank fusion (RRF), followed by cross-encoder reranking.
- **Grounded answering:** uses a structured answer contract, an answerability gate, and a separate claim-grounding verification step.
- **Abstention and safe fallback:** unapproved evidence is excluded; when evidence or provider validation is insufficient, the system abstains or returns approved source passages rather than releasing an unverified draft.
- **Inspectable UI:** Gradio views for Ask, Evidence, Trace, Evaluation, Algorithm Lab, and About.
- **Operational checks:** CLI readiness/status commands and HTTP `/healthz` and `/readyz` probes.
- **Automated quality checks:** pytest, Ruff, mypy, locked dependency checks, and GitHub Actions CI.

## Architecture

```text
MIT OCW source assets
        |
        v
Source manifest + SHA-256 integrity checks
        |
        v
PDF / VTT extraction
        |
        v
Page- or timestamp-aware units + provenance
        |
        v
Candidate chunks -> human review -> explicit eligibility decision
                                      |
                                      v
                           BM25 + dense retrieval
                                      |
                                      v
                                RRF fusion
                                      |
                                      v
                            Cross-encoder reranker
                                      |
                                      v
                              Answerability gate
                                      |
                                      v
                        OpenAI-compatible LLM provider
                                      |
                                      v
                         Independent claim verification
                                      |
                                      v
                       Cited answer, sources, or abstention
```

The diagram describes the implemented design, not a claim that the production corpus is currently open. The review/eligibility gate remains closed until canonical evidence is explicitly approved.

## Implementation and limitations

| Area | Current state |
|---|---|
| Source manifest and integrity validation | Implemented |
| VTT-to-timestamped-JSONL conversion | Implemented |
| Page-aware PDF-to-Markdown extraction | Implemented |
| Chunking and provenance metadata | Implemented |
| BM25, dense retrieval, RRF, reranking | Implemented; diagnostic retrieval is available |
| Answer contracts, answerability checks, claim verification | Implemented and tested |
| Gradio interface and readiness endpoints | Implemented |
| Production answer corpus | **Blocked:** no eligible canonical child passages at this checkpoint |
| Final evaluation | **Blocked:** human-reviewed labels, valid canonical passage IDs, and a frozen leakage-safe split are prerequisites |
| Production deployment/release | Not yet accepted; depends on corpus and evaluation gates |

Do not interpret passing unit tests or exploratory retrieval metrics as proof of production answer quality. Diagnostic retrieval may inspect experimental chunks, but it does not authorize those chunks for user-facing answers.

## Source material

The tutor is scoped to **MIT OpenCourseWare 6.046J Design and Analysis of Algorithms, Spring 2015, Lecture 6: “Randomization: Matrix Multiply, Quicksort,”** taught by Srinivas Devadas.

- [Official lecture resource page](https://ocw.mit.edu/courses/6-046j-design-and-analysis-of-algorithms-spring-2015/resources/lecture-6-randomization-matrix-multiply-quicksort/)
- [Typed lecture notes PDF](https://ocw.mit.edu/courses/6-046j-design-and-analysis-of-algorithms-spring-2015/cb55cb123a557eed0738a1187a452c24_MIT6_046JS15_lec06.pdf)
- [Handwritten lecture notes PDF](https://ocw.mit.edu/courses/6-046j-design-and-analysis-of-algorithms-spring-2015/7d59cd5e4d6cb323739deff687ed1bff_MIT6_046JS15_writtenlec6.pdf)
- [Lecture video](https://archive.org/download/MIT6.046JS15/MIT6_046JS15_lec06_300k.mp4)

The source manifest lives at `corpus/manifest.yaml`; source notes and attribution details are in [`docs/sources.md`](docs/sources.md). Raw media belongs in the git-ignored `corpus/raw/` directory and must not be committed.

## Quick start

### Prerequisites

- Windows, macOS, or Linux
- Python **3.12**
- [uv](https://docs.astral.sh/uv/) for Python and dependency management
- An OpenAI-compatible endpoint: either a local [Ollama](https://ollama.com/) server or a Groq API key

### Install

Clone the repository and enter the project directory:

```powershell
git clone https://github.com/Harjotsingh0311/algolens.git
Set-Location algolens
```

Install the locked dependencies:

```powershell
uv sync --all-groups --locked
uv lock --check
```

Create local configuration:

```powershell
Copy-Item .env.example .env
```

Edit `.env` with your preferred provider as described below. Never commit `.env` or API keys.

### Launch the app

```powershell
uv run python app/app.py
```

Open the local URL printed by Gradio in the terminal. The UI can launch while the corpus is in safe mode. In the current repository state, asking a question should explain that generation is locked because there are no eligible canonical passages; **this is expected, not an installation failure**.

## Configuration

The checked-in `.env.example` contains:

```dotenv
GROQ_API_KEY=
LLM_PROVIDER=groq
ALGOLENS_MODEL=openai/gpt-oss-120b
OLLAMA_BASE_URL=http://localhost:11434/v1
```

Choose one provider:

**Groq**

Set `LLM_PROVIDER=groq`, fill in `GROQ_API_KEY`, and optionally set `ALGOLENS_MODEL`. The default model is `openai/gpt-oss-120b`.

**Ollama**

Start Ollama locally, pull a model you have available, and set `LLM_PROVIDER=ollama`. Set `ALGOLENS_MODEL` to the model name you pulled. The default OpenAI-compatible endpoint is `http://localhost:11434/v1`; override `OLLAMA_BASE_URL` if your server uses another address.

Optional fallback-provider settings use the `ALGOLENS_FALLBACK_PROVIDER`, `ALGOLENS_FALLBACK_MODEL`, `ALGOLENS_FALLBACK_BASE_URL`, `ALGOLENS_FALLBACK_API_KEY`, and `ALGOLENS_FALLBACK_TIMEOUT_SECONDS` environment variables. Supported fallback providers are `groq` and `ollama`. Fallback is attempted after a primary-provider failure or invalid citations; if all providers fail, a failed draft is not released.

### Answer cache

Set `ALGOLENS_CACHE_PATH` to choose a writable SQLite cache file. By default, the cache is stored under the operating system's temporary directory. It is bounded to 256 entries with a seven-day TTL. Cache keys hash the question, evidence, model/corpus namespace, and partial-answer mode; raw questions and API keys are not stored as cache keys. Cache hits still pass through the usual answer and claim-verification checks.

## Commands

Run commands from the repository root:

| Command | Purpose |
|---|---|
| `uv run python -m algolens.cli status` | Check source integrity, corpus approval, and evaluation readiness |
| `uv run python -m algolens.cli ingest` | Verify sources and build separate derived extraction artifacts |
| `uv run python -m algolens.cli review-check` | Verify pages 5–6 review metadata, source/candidate hashes, and canonical chunk consistency without enabling retrieval |
| `uv run python -m algolens.cli index` | Smoke-test the production index path; blocks if no approved passages exist |
| `uv run python -m algolens.cli index --diagnostic` | Inspect retrieval on experimental chunks only |
| `uv run python -m algolens.cli eval` | Check whether final evaluation prerequisites are met |
| `uv run python -m algolens.cli eval --diagnostic --retriever bm25` | Run exploratory retrieval metrics; does not authorize answer generation |
| `uv run python app/app.py` | Start the Gradio app |

The CLI writes reports beneath `corpus/processed/generated/`, `index/`, and `eval/results/` as applicable. `review-check` writes `corpus/processed/generated/reviewed_candidate_audit.json`; it is an integrity audit only and does not modify canonical chunks or approval flags. Ingestion also creates separate derived artifacts and does not automatically promote chunks or modify review approvals.

## Corpus approval and safe mode

AlgoLens requires all of the following on a canonical child passage before it can be used for answering:

1. A reviewed/verified/approved `review_status`.
2. `eligible_for_answer: true`.
3. `retrieval_eligible: true`.

A candidate being extracted, chunked, cited in a draft, or present in an experimental index does **not** satisfy these conditions. Do not weaken the gates to make the app answer. Review the source content, record the decision explicitly, then restart the app so its cached runtime reads the updated corpus.

At this checkpoint, the printed pages 5–6 transcription has project-owner approval, and its two parent/child chunks are present in canonical reviewed-chunk files, but they remain retrieval-disabled pending a separate eligibility decision. Page 3–4 Quicksort candidates remain pending owner review. No canonical child passage currently satisfies all production signals.

Operational endpoints:

- `GET /healthz` returns HTTP 200 when the process is up.
- `GET /readyz` returns HTTP 200 only when canonical evidence and the grounded runtime are ready. HTTP 503 in safe mode is intentional.

## Randomized Quicksort lab

Run the lecture's algorithm as a reproducible experiment and inspect comparison counts:

```powershell
uv run python -m algolens.algorithm_lab --n 100 --trials 100 --seed 42
uv run python -m algolens.algorithm_lab --n 20 --trials 10 --seed 42 --trace
```

The lab records pivot-partition traces and empirical comparison counts. It is a teaching utility,
not a source of approved RAG evidence; see [the lab notes](docs/algorithm-lab.md).

## Algorithm Lab

The **Algorithm Lab** tab runs a seeded randomized Quicksort simulation, records each partition,
and reports empirical comparison counts across repeated shuffled inputs. It is a teaching
demonstration, not approved lecture evidence and not a replacement for the gold evaluation.

Run the same experiment from the terminal:

```powershell
uv run python -m algolens.algorithm_lab --n 100 --trials 100 --seed 42
```

See [docs/algorithm-lab.md](docs/algorithm-lab.md) for the interpretation and trace option.

## Evaluation status

The active `eval/gold/questions_v0.jsonl` file still contains draft questions. A separate 80-question candidate bank and per-question review worksheet exist, but the candidate bank has not been promoted to the final gold set. The 50-question development / 30-question test split is not yet frozen, and gold passage IDs must map to approved canonical chunks.

Existing retrieval reports are exploratory diagnostics—not final benchmark results. Final evaluation remains blocked until question labels are human-reviewed, passage IDs match the approved corpus, the split is frozen, and acceptance checks pass. Thresholds must be calibrated on development data, then evaluated once on the held-out test set.

## Repository layout

```text
app/                         Gradio UI and HTTP readiness endpoints
src/algolens/                Ingestion, retrieval, answering, providers, evaluation
corpus/manifest.yaml         Source manifest and integrity metadata
corpus/raw/                  Local source PDFs/VTT/media (git-ignored)
corpus/processed/            Derived and canonical corpus artifacts
corpus/experiments/          Non-canonical extraction/chunking experiments
eval/gold/                   Draft questions and candidate evaluation assets
eval/results/                Diagnostic and evaluation reports
tests/                       Automated tests
docs/sources.md              Source catalogue and attribution
CONTENT-LICENSE.md           Third-party course-content handling
Makefile                     Common local development targets
pyproject.toml / uv.lock     Project configuration and locked dependencies
```

## Quality checks

The same checks run in local development and GitHub Actions CI:

```powershell
uv sync --all-groups --locked
uv lock --check
uv run ruff check src tests app
uv run ruff format --check src tests app
uv run mypy src
uv run pytest -q
```

The latest verified main-branch CI checkpoint (26 October 2026) passed **264 tests**, Ruff lint/format checks, and strict mypy across 31 source files. CI reported one non-fatal Starlette/httpx deprecation warning. These are code-quality results, not proof of production readiness or answer quality.

## Licensing and attribution

- **AlgoLens source code:** MIT License; see [`LICENSE`](LICENSE).
- **Course materials:** the project records MIT OpenCourseWare attribution and the proposed CC BY-NC-SA 4.0 terms in [`CONTENT-LICENSE.md`](CONTENT-LICENSE.md). Verify the applicable terms for each source before redistribution.
- Do not commit raw videos or PDFs. Review processed-corpus redistribution against the applicable source terms before publishing derived material.

## Roadmap

1. Finish human review of source-grounded candidate passages.
2. Make and test explicit retrieval-eligibility decisions for canonical passages.
3. Promote and review the candidate question bank; map labels to approved passage IDs and freeze the dev/test split.
4. Validate provider behavior and claim verification on human-labelled examples.
5. Calibrate thresholds on development data and run final evaluation once on the held-out test set.
6. Complete ablations, operational acceptance checks, and deployment only after the preceding gates pass.
