---
title: AlgoLens
emoji: "🔎"
colorFrom: indigo
colorTo: blue
sdk: gradio
python_version: "3.12"
app_file: app/app.py
pinned: false
---

# AlgoLens

A citation-first RAG tutor for MIT 6.046J Lecture 6: Randomization, Matrix
Multiply, and Quicksort.

AlgoLens retrieves only approved lecture passages, fuses lexical and semantic
search, reranks results, calibrates whether a question is answerable, generates a
structured response through Groq or Ollama, and independently checks each cited
claim before releasing it. When evidence or verification is insufficient, it
abstains or shows sources only.

## Project status

The proposal's randomized-Quicksort path is implemented end to end.

- Five MIT OCW source assets are SHA-256 pinned and locally verified.
- The production corpus contains 32 approved child passages and 12 parents.
- The versioned benchmark contains 80 source-verified questions: 50 development
  and 30 public test questions, including 15 unanswerable requests.
- BM25, dense retrieval, reciprocal-rank fusion, cross-encoder reranking, and
  two-source pairing are implemented and evaluated.
- The calibrated answerability gate combines score thresholds with deterministic
  scope guards for prompt injection, unsupported measurements, and unrelated topics.
- Generated claims require valid passage IDs and independent NLI support.
- The Gradio app includes Ask, Evidence, Trace, Evaluation, and Algorithm Lab views,
  plus `/healthz` and `/readyz` probes.

The source and question review was AI-assisted and project-owner-authorized, not an
independent human annotation exercise. That distinction is retained in every promoted
record and evaluation report.

## Evaluation snapshot

| Retriever | Overall question recall@5 | Test question recall@5 | Test MRR@10 |
|---|---:|---:|---:|
| BM25 | 0.908 | **0.870** | 0.451 |
| Dense | 0.785 | 0.739 | 0.482 |
| Hybrid RRF | 0.846 | 0.739 | 0.512 |
| Hybrid + reranker | 0.877 | 0.826 | **0.565** |
| Hybrid + reranker + pairing | **0.908** | 0.783 | 0.549 |

On the 30-question public test split, the answerability gate achieved AUROC 1.000,
0.933 accuracy, and a 0.000 wrong-answer rate on unanswerable questions. It accepted
21 of 23 answerable questions (0.913). This is a pre-generation gate result. In the
full retrieval → generation → NLI run, 18 of 23 answerable responses were released
(0.783), while all seven unanswerable requests were safely refused. This is one
question short of the proposal's 0.80 target. The required
no-retrieval baseline answered all seven unanswerable requests and had zero citation
recall. These conservative end-to-end results are reported rather than hidden.

See [the final evaluation](eval/results/final_evaluation.md) for metric definitions,
ablations, limitations, hashes, and the live grounded-answer smoke test.

## Architecture

```text
MIT OCW assets -> hash verification -> page/timestamp chunks -> source review
       -> BM25 + dense -> RRF -> cross-encoder -> optional source pairing
       -> answerability + scope guard -> structured LLM draft
       -> citation validation -> windowed NLI verification -> answer or abstention
```

Production evidence must have all three signals: an approved review status,
`eligible_for_answer: true`, and `retrieval_eligible: true`. Experimental files never
become answer evidence merely by being present in the repository.

## Quick start

Requirements: Python 3.12 and [uv](https://docs.astral.sh/uv/).

```powershell
git clone https://github.com/Harjotsingh0311/algolens.git
Set-Location algolens
uv sync --all-groups --extra semantic --locked
Copy-Item .env.example .env
uv run python app/app.py
```

For Groq, set `LLM_PROVIDER=groq`, `GROQ_API_KEY`, and optionally
`ALGOLENS_MODEL`. For a local OpenAI-compatible Ollama server, set
`LLM_PROVIDER=ollama`, `ALGOLENS_MODEL`, and `OLLAMA_BASE_URL`.

Never commit `.env` or API keys. Hosted deployments must configure secrets in the
hosting platform.

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
| `uv run python -m algolens.evaluation.review_decisions --write-template` | Create an unapproved review-decision template |
| `uv run python -m algolens.evaluation.review_decisions` | Validate explicit human review records before creating a reviewed gold set |
| `uv run python -m algolens.evaluation.answerability_runner --scores eval/results/answerability_scores.jsonl` | Evaluate supplied scores against reviewed gold labels |
| `uv run python -m algolens.evaluation.gold_audit` | Audit draft gold questions and prioritize evidence/review blockers |
| `uv run python -m algolens.ingest.formula_quality` | Detect known formula extraction defects; warnings require PDF review |
| `uv run python tools/run_retrieval_ablations.py` | Reproduce all 34 retrieval/representation ablations |
| `uv run python -m tools.run_generation_evaluation --split test --mode all` | Compare grounded generation with the no-retrieval baseline |
| `uv run python app/app.py` | Start the Gradio app |

The CLI writes reports beneath `corpus/processed/generated/`, `index/`, and `eval/results/` as applicable. `review-check` writes `corpus/processed/generated/reviewed_candidate_audit.json`; it is an integrity audit only and does not modify canonical chunks or approval flags. Ingestion also creates separate derived artifacts and does not automatically promote chunks or modify review approvals.

## Corpus approval and safe mode

AlgoLens requires all of the following on a canonical child passage before it can be used for answering:

1. A reviewed/verified/approved `review_status`.
2. `eligible_for_answer: true`.
3. `retrieval_eligible: true`.

A candidate being extracted, chunked, cited in a draft, or present in an experimental index does **not** satisfy these conditions. Do not weaken the gates to make the app answer. Review the source content, record the decision explicitly, then restart the app so its cached runtime reads the updated corpus.

At this checkpoint, all 32 canonical child passages satisfy the production signals.
They cover the randomized-Quicksort scope using 28 timestamped caption passages and
four typed-note passages. The review was AI-assisted and project-owner-authorized;
independent human sign-off remains a separate release requirement.

Operational endpoints:

- `GET /healthz` returns HTTP 200 when the process is up.
- `GET /readyz` returns HTTP 200 only when canonical evidence and the grounded runtime are ready. HTTP 503 in safe mode is intentional.

## Randomized Quicksort lab

Run the lecture's algorithm as a reproducible experiment and inspect comparison counts:

```powershell
# Verify sources, approved corpus, and reviewed benchmark
uv run python -m algolens.cli status

# Rebuild derived extraction artifacts after hash verification
uv run python -m algolens.cli ingest

# Smoke-test the production retrieval index
uv run python -m algolens.cli index

# Run final retriever evaluations
uv run python -m algolens.cli eval --retriever bm25
uv run python -m algolens.cli eval --retriever hybrid-reranked-paired

# Reproduce 34 retrieval ablations
uv run python tools/run_retrieval_ablations.py

# Reproduce grounded generation and the no-retrieval baseline
uv run python -m tools.run_generation_evaluation --split test --mode all

# Run the seeded randomized-Quicksort teaching lab
uv run python -m algolens.algorithm_lab --n 100 --trials 100 --seed 42
```

Raw course media is intentionally Git-ignored. Download it from the URLs in
`corpus/manifest.yaml`; `status` and `ingest` reject missing or mismatched hashes.

## Source material

The tutor is scoped to MIT OpenCourseWare 6.046J, Spring 2015, Lecture 6, taught by
Srinivas Devadas.

- [Lecture resource page](https://ocw.mit.edu/courses/6-046j-design-and-analysis-of-algorithms-spring-2015/resources/lecture-6-randomization-matrix-multiply-quicksort/)
- [Typed lecture notes](https://ocw.mit.edu/courses/6-046j-design-and-analysis-of-algorithms-spring-2015/cb55cb123a557eed0738a1187a452c24_MIT6_046JS15_lec06.pdf)
- [Handwritten notes](https://ocw.mit.edu/courses/6-046j-design-and-analysis-of-algorithms-spring-2015/7d59cd5e4d6cb323739deff687ed1bff_MIT6_046JS15_writtenlec6.pdf)
- [Lecture video](https://archive.org/download/MIT6.046JS15/MIT6_046JS15_lec06_300k.mp4)

MIT OCW source material remains under CC BY-NC-SA 4.0. Repository code is MIT
licensed. See [source attribution](docs/sources.md) and [LICENSE](LICENSE).

## Quality checks

```powershell
uv lock --check
uv run ruff format --check src tests app tools
uv run ruff check src tests app tools
uv run mypy src
uv run pytest -q
```

## Repository map

```text
app/                         Gradio/FastAPI application
corpus/manifest.yaml         Source inventory and pinned hashes
corpus/processed/            Reviewed and generated corpus artifacts
eval/gold/                   Versioned reviewed question set and decisions
eval/results/                Final metrics, rankings, and ablations
eval/source_review/          Caption/audio spot-check evidence
src/algolens/                Retrieval, answering, verification, and CLI code
tests/                       Unit, integration, and HTTP tests
tools/                       Promotion, refresh, and ablation utilities
```

## Remaining limitations

- The public test split is version-controlled, not a secret holdout.
- Independent human review would strengthen the source and question labels.
- The approved corpus covers randomized Quicksort rather than all Lecture 6 topics.
- The NLI verifier is a conservative model-based check, not a proof of truth.
- A live hosted Space requires an account-level deployment and secret configuration;
  local production readiness does not itself publish the app.
