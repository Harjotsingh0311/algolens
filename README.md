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

<div align="center">

# 🔎 AlgoLens

### Your algorithm lecture, searchable. Your answers, accountable.

**A citation-first RAG tutor for MIT 6.046J — Lecture 6: Randomization, Matrix Multiply & Quicksort.**

Learn from lecture evidence, inspect where an answer came from, and get an honest abstention when the sources cannot support a claim.

<p>
  <a href="https://github.com/Harjotsingh0311/algolens/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/Harjotsingh0311/algolens/actions/workflows/ci.yml/badge.svg"></a>
  <img alt="Python 3.12" src="https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white">
  <img alt="Gradio" src="https://img.shields.io/badge/UI-Gradio-F97316">
  <img alt="License" src="https://img.shields.io/badge/License-MIT-green.svg">
  <img alt="Project stage" src="https://img.shields.io/badge/Stage-Research%20prototype-orange">
</p>

[Explore the code](https://github.com/Harjotsingh0311/algolens) · [Read the proposal gap audit](docs/proposal-gap-audit-2026-10-27.md) · [Open an issue](https://github.com/Harjotsingh0311/algolens/issues)

</div>

---

> [!IMPORTANT]
> **Current state: safe mode is intentional.** The application and retrieval/answering components are implemented, but the canonical evidence has not yet passed every production approval gate. AlgoLens must not generate answers from pending, experimental, or retrieval-disabled passages. This is a deliberate safety property, not a broken demo.

## ✨ The idea

Most study chatbots optimize for producing an answer. **AlgoLens optimizes for showing when an answer is justified.**

Ask a question about the lecture. The system retrieves relevant passages, combines lexical and semantic search, reranks the evidence, checks answerability, and validates the claims and citations before returning a grounded response. When the evidence is insufficient, it should abstain rather than invent.

## 🧭 How it works

```text
MIT OCW lecture notes + timestamped captions
                  │
                  ▼
       Hash-checked source manifest
                  │
                  ▼
    Page-aware PDF / timestamped VTT extraction
                  │
                  ▼
      Provenance-preserving parent/child chunks
                  │
                  ▼
        Human review + explicit eligibility
                  │
                  ▼
       ┌──────────┴──────────┐
       ▼                     ▼
   BM25 search          Dense retrieval
       └──────────┬──────────┘
                  ▼
        Reciprocal-rank fusion (RRF)
                  ▼
          Cross-encoder reranking
                  ▼
            Answerability gate
                  ▼
       OpenAI-compatible LLM provider
                  ▼
      Claim and citation verification
                  ▼
        Cited answer — or abstention
```

The diagram describes the intended pipeline; it does **not** mean the production corpus is currently approved.

## 🧰 What’s inside

| Component | What it contributes |
|---|---|
| **Source ingestion** | Manifest validation, source hashes, PDF extraction, timestamped VTT conversion |
| **Provenance-aware chunks** | Page/timestamp citations and parent-child context |
| **Hybrid retrieval** | BM25 + dense retrieval, Reciprocal Rank Fusion, cross-encoder reranking |
| **Grounded answering** | Structured answer contract, answerability gate, claim-level checks |
| **Provider resilience** | OpenAI-compatible provider integration, fallback behavior and bounded SQLite cache |
| **Study interface** | Gradio Ask, Evidence, Trace, Evaluation, Algorithm Lab and About views |
| **Algorithm Lab** | Seeded randomized Quicksort simulation, partition trace and comparison counts |
| **Quality tooling** | Pytest, Ruff, mypy, CI, source-review packets, gold audit and formula-quality audit |

## 🛡️ Safety is a feature

A passage is not answer-ready merely because it was extracted or appears in a search result. A canonical child passage must satisfy all three conditions:

- `review_status` records an accepted review state.
- `eligible_for_answer: true`.
- `retrieval_eligible: true`.

Diagnostic corpora are useful for debugging retrieval, but they do not authorize user-facing answers. The code must not promote draft labels, infer human approval, or open the gate just to make the interface look more impressive.

## 🚦 Project status

| Area | Status |
|---|---|
| Core ingestion, chunking and provenance | Implemented |
| BM25, dense retrieval, RRF and reranking | Implemented; production use depends on evidence approval |
| Answer contract, provider integration and claim checks | Implemented and tested |
| Gradio interface and health/readiness endpoints | Implemented |
| Caption timestamp spot-checks against video | Human verification still required |
| Formula extraction review against original PDF | Human verification still required |
| Canonical answer-eligible corpus | **Blocked pending explicit eligibility decisions** |
| Reviewed gold evaluation set and frozen dev/test split | **Blocked pending human labels and evidence mapping** |
| Final ablations and release acceptance | Not yet accepted |

Passing CI proves code quality checks ran successfully; it does not prove answer quality. Exploratory metrics must not be presented as final benchmark results.

## 🚀 Run it locally

### Requirements

- Python 3.12
- [uv](https://docs.astral.sh/uv/)
- A supported OpenAI-compatible provider: Groq or local Ollama

### Install

```powershell
git clone https://github.com/Harjotsingh0311/algolens.git
Set-Location algolens
uv sync --all-groups --locked
Copy-Item .env.example .env
```

Edit `.env` and configure **one** provider. For Groq, set `LLM_PROVIDER=groq` and provide `GROQ_API_KEY`. For local Ollama, set `LLM_PROVIDER=ollama` and select a model available on your machine. Never commit secrets or your `.env` file.

### Launch

```powershell
uv run python app/app.py
```

Open the local URL printed by Gradio. The UI can start in safe mode; if the corpus has no eligible canonical passages, question answering should remain locked. That behavior is expected until evidence approval is complete.

## 🧪 Useful commands

Run from the repository root.

| Command | Purpose |
|---|---|
| `uv run python -m algolens.cli status` | Check source integrity, corpus approval and evaluation readiness |
| `uv run python -m algolens.cli ingest` | Verify sources and build derived extraction artifacts |
| `uv run python -m algolens.cli review-check` | Audit reviewed candidate metadata without enabling retrieval |
| `uv run python -m algolens.cli index --diagnostic` | Inspect retrieval on experimental chunks only |
| `uv run python -m algolens.cli eval --diagnostic --retriever hybrid-reranked` | Run exploratory retrieval diagnostics |
| `uv run python -m algolens.evaluation.gold_audit` | Audit draft gold questions and prioritize review blockers |
| `uv run python -m algolens.evaluation.review_decisions --write-template` | Generate an unapproved review-decision template |
| `uv run python -m algolens.ingest.formula_quality` | Scan extracted notes for known formula-corruption patterns |
| `uv run python -m algolens.algorithm_lab --n 100 --trials 100 --seed 42` | Run a reproducible Quicksort experiment |

Diagnostic commands do not approve evidence or authorize answer generation.

## 🧱 Quality checks

```powershell
uv lock --check
uv run ruff check src tests app
uv run ruff format --check src tests app
uv run mypy src
uv run pytest -q
```

GitHub Actions runs the same core checks on proposed changes. See the [CI workflow](https://github.com/Harjotsingh0311/algolens/actions/workflows/ci.yml).

## 📚 Source material

AlgoLens is scoped to MIT OpenCourseWare **6.046J Design and Analysis of Algorithms, Spring 2015, Lecture 6: “Randomization: Matrix Multiply, Quicksort,”** taught by Srinivas Devadas.

- [Official lecture resource page](https://ocw.mit.edu/courses/6-046j-design-and-analysis-of-algorithms-spring-2015/resources/lecture-6-randomization-matrix-multiply-quicksort/)
- [Typed lecture notes PDF](https://ocw.mit.edu/courses/6-046j-design-and-analysis-of-algorithms-spring-2015/cb55cb123a557eed0738a1187a452c24_MIT6_046JS15_lec06.pdf)
- [Handwritten lecture notes PDF](https://ocw.mit.edu/courses/6-046j-design-and-analysis-of-algorithms-spring-2015/7d59cd5e4d6cb323739deff687ed1bff_MIT6_046JS15_writtenlec6.pdf)
- [Lecture video](https://archive.org/download/MIT6.046JS15/MIT6_046JS15_lec06_300k.mp4)

The source manifest is `corpus/manifest.yaml`; attribution and source details are in [docs/sources.md](docs/sources.md). Raw PDFs and videos must not be committed. Check the applicable course-content terms before redistributing derived material.

## 🗺️ Roadmap

- [ ] Verify caption timestamps against the lecture video.
- [ ] Review extracted formulas against the original notes PDF.
- [ ] Make explicit eligibility decisions for canonical passages.
- [ ] Human-review the 80-question candidate set and map gold passages to approved canonical evidence.
- [ ] Freeze the 50-question development / 30-question test split.
- [ ] Run controlled retrieval ablations, calibrate abstention on development data, and evaluate once on held-out test data.
- [ ] Complete operational acceptance checks before enabling release.

## 📄 Licensing

- **Code:** MIT License — see [LICENSE](LICENSE).
- **Course content:** see [CONTENT-LICENSE.md](CONTENT-LICENSE.md) and the source-specific terms before redistributing course-derived material.

---

<div align="center">

**Built around a simple principle: every answer should earn its citations.**

</div>
