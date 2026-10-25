# AlgoLens - Proposal Execution Tracker

Last updated: 2026-10-26
Project: MIT 6.046J Lecture 6 citation-first RAG tutor
Purpose: Track proposal requirements beside implementation evidence.

## Proposal workstreams side by side

| Proposal stage | Requirement | Current evidence | Status | Next acceptance gate |
|---|---|---|---|---|
| Turn 0 | Repository, concept, manifest, developer tooling, CI and deployment eligibility | Project scaffold, manifest, tests and developer tooling exist. | Mostly complete | Verify current Hugging Face/ZeroGPU eligibility. |
| Turn 1 | Fetch and parse notes/transcript; validate locators | Typed-notes PDF is hash-pinned; captions are parsed into timestamped JSONL; extraction comparisons exist. | In progress | Finish source audit and caption-alignment review. |
| Turn 2 | Baseline, 30-question gold set and evaluation harness | BM25, dense and RRF evaluation reports exist; 30-question gold set is draft-labelled. | Implemented, provisional | Human-review labels; finalize dev/test split and final reports. |
| Turn 3 | Teach-unit chunks, hybrid retrieval, RRF, reranking, context headers and ablations | BM25/dense retrieval, RRF, reranking, chunk metadata, CLI indexing, and Gradio runtime composition exist. Production indexing remains blocked because no canonical child passage has all three approval signals. | In progress | Complete source review and a separate retrieval-eligibility decision; then test on approved evidence and run systematic retrieval/reranking ablations. |
| Turn 4 | Answerability gate, abstention and risk-coverage evaluation | Gate, metrics and diagnostic runner implemented. All production decisions currently abstain because available evidence is ineligible. Gold labels remain unreviewed. | In progress | Human-review labels, define a leakage-safe dev/test split, calibrate on development data and evaluate once on held-out test data. |
| Turn 5 | Generation contract, grounded citations, claim verification, model adapter and cache | Structured contracts, answer service, OpenAI-compatible provider, NLI grounding verifier, and a grounded-answer wrapper exist. A synthetic positive-path integration test passes; real-provider success, threshold calibration, and caching are not yet validated. | In progress | Validate the provider with safe test configuration, review NLI decisions against human-labelled claims, calibrate on development data, and implement caching. |
| Turn 6 | Gradio UI, live deployment, probes and operational documentation | Gradio UI and UI tests now exist. Live deployment, health probes, and end-to-end production validation remain outstanding because the approved corpus is empty for answer generation. | In progress | Complete local corpus and runtime acceptance gates first; then add health probes, deploy, and validate the live demo. |
| Turn 7 | Two-voice pairing, Algorithm Lab, handwritten notes, Tier 2 and final 80-question evaluation | Stretch scope is documented; these features are not complete. | Not started | Begin after must-have features and final evaluation are sound. |

## Task ledger

| Task | Evidence/result | State |
|---|---|---|
| Project scaffold, manifest and developer tooling | Existing project files and Git history | Complete |
| Source integrity | Original typed-notes PDF hash matches manifest and review metadata | Verified |
| Experimental PDF extraction and chunks | Experimental extracts and JSONL artifacts retained separately | Complete as an experiment; extraction limitations remain documented |
| BM25, dense retrieval and RRF evaluation | Existing retrieval tools and provisional comparison | Implemented; diagnostic only |
| Gold question set | 30 questions with draft labels | Human review pending |
| Expectations transcription review | Printed pages 5-6 checked against the supplied PDF | Approved for integration |
| Reviewed-candidate parser and metadata validation | Parser and hash/approval safety checks | Tested |
| Reviewed-source chunk artifact | Two parent and two child chunks; page-specific citations | Validated; retrieval disabled |
| Final project quality gate | Full tests, lint, formatting, type, lockfile and whitespace checks | 221 tests passed; Ruff lint and format checks passed; Mypy passed for 26 source files. The checkpoint was committed and pushed to GitHub as `fa1756d`; local branch tracked `origin/main`. | Verified 2026-10-26 |
| Runtime hybrid retrieval | HybridIndex fuses BM25 and dense rankings with RRF; 8 focused tests passed. | Implemented and tested as a reusable component |
| Cross-encoder reranking | CrossEncoderReranker is implemented with lazy model loading and eligibility checks; 11 reranker unit tests passed, including checkpoint-ID regression. | Component implemented; single real-model diagnostic smoke query passed; systematic evaluation pending |
| Runtime query pipeline | RetrievalPipeline connects HybridIndex to CrossEncoderReranker; 8 focused tests passed for flow, metadata preservation and eligibility controls. | Reusable component implemented; application endpoint/UI wiring pending |
| Abstention and grounded generation | Core services, provider adapter, NLI verifier and runtime composition implemented; positive approved-evidence end-to-end validation and threshold calibration remain. | In progress |

## Evaluation interpretation

Recorded Recall@k, MRR and nDCG results are provisional diagnostics because the gold labels have not all been human-reviewed. They must not be reported as final benchmark results.

The captions are auto-generated and are not independently verified against the video. The reviewed typed-notes transcription covers only printed pages 5-6; it does not approve the full PDF extraction or caption corpus.

## Immediate next gates

1. Use small Git checkpoints, inspect diffs before pushing, and keep credentials out of Git history.
2. Keep candidate pages 3-4 and all other unreviewed evidence ineligible until source review and approval are explicitly completed.
3. A synthetic positive-path integration test with an explicitly approved fixture and fake verifier passes; validate the real approved-corpus path only after retrieval eligibility is separately approved.
4. Validate provider integration, review the NLI verifier against human-labelled claims, calibrate only on development data, and implement caching.
5. The Gradio UI and configuration path are implemented; add deployment probes and operational documentation after the backend and corpus acceptance gates pass.
6. Complete the human-reviewed gold set, held-out evaluation, final quality gate and proposal acceptance checklist.

## Latest runtime retrieval validation (2026-10-25)

- **Automated quality gate:** 100 tests passed; Ruff lint passed; Ruff format check passed (71 files formatted); Mypy passed for 16 source files; `uv lock --check` passed.
- **Real-model smoke test:** passed using `sentence-transformers/all-MiniLM-L6-v2` and `cross-encoder/ms-marco-MiniLM-L6-v2`, both resolved to CUDA.
- **Diagnostic corpus:** 32 experimental child chunks; 5 results returned. Citation/provenance fields were preserved, and all results remained ineligible for answer generation.
- **Timing observations:** BM25 index build ~0.005 s; dense index build including model and embeddings ~37.124 s; first query including lazy cross-encoder loading ~52.598 s; second warm query ~0.114 s. These are smoke-test observations, not benchmark results.
- **Evidence boundary:** experimental chunks remain unreviewed and must not be used as answer evidence. The smoke test does not demonstrate answer quality or a retrieval improvement.
- **Remaining work:** review and approve source-grounded chunks, validate the gold set, run systematic retrieval/reranking evaluation and ablations, then integrate retrieval with answerability gating, citation verification, and the application interface.

## Candidate chunk review - Quicksort pages 3-4 (2026-10-25)

- **Artifacts:** one parent and three child candidates created under `corpus/processed/reviewed_candidates/`.
- **Source verification:** original typed-notes PDF SHA-256 matches the pinned manifest value; candidate Markdown hash is recorded in its review metadata.
- **Citations:** parent covers printed pages 3-4; children cite page 3, page 4, and page 4 respectively.
- **Validation:** stored-file Unicode audit, required-equation checks, parent/child links, and answer-eligibility checks passed. Review report synchronized with saved JSONL word counts.
- **Design note:** the third child is 70 words, below the nominal 120-200-word target. Its separate heading is retained as a source-boundary exception pending review.
- **Approval status:** candidate transcription and chunk review remain pending; all records remain retrieval-ineligible.
- **Corpus status:** canonical reviewed chunks and experimental extraction files were not modified. Candidate artifacts are version-controlled; project-owner approval remains pending and retrieval stays disabled.

## Turn 4 - Answerability gate and diagnostic evaluation

- **Gate implementation:** `src/algolens/answerability.py` exposes `AnswerabilityGate.assess()` and `decide(hits)`, with answer, partial, and abstain decisions; 18 focused unit tests pass.
- **Evaluation metrics:** `src/algolens/evaluation/answerability_metrics.py` calculates coverage, risk among accepted questions, wrong-answer rate on unanswerable questions, false-refusal rate, and a score-ranked risk-coverage curve/AURC; 18 focused unit tests pass.
- **Diagnostic runner:** `tools/evaluate_answerability_gate.py` evaluates the current 30-question draft set with the real retrieval/reranking pipeline; report saved to `eval/results/answerability_gate_diagnostic.json`.
- **Exploratory result:** provisional cutoffs produced 0.80 score-based coverage, 0.0417 risk among accepted questions, and 0.0230 AURC on the draft labels. These are not calibrated or held-out metrics.
- **Safety result:** actual gate decisions abstained for all 30 questions because every available passage is unapproved. No answers were generated.
- **Evidence limitation:** all 30 labels remain `draft_needs_human_review`; there is no validated development/test split. Do not freeze a threshold or claim production performance from these metrics.
- **Current state:** gate and metric code implemented; diagnostic evaluation completed. Remaining work includes reviewing labels, defining a leakage-safe split, calibrating only on development data, and evaluating on the held-out test set once.

## Turn 5 - Structured answer contract and generation boundary

- **Contracts:** `src/algolens/contracts.py` defines validated Passage, Hit, Claim, Answer, and citation-reference models.
- **Answer service:** `src/algolens/answering.py` filters evidence, applies the answerability gate, validates citation IDs, and abstains safely on errors.
- **Provider adapter:** `src/algolens/providers.py` implements an OpenAI-compatible chat-completions adapter, with regression tests for `LLM_PROVIDER` and `OLLAMA_BASE_URL` compatibility. Unit tests use controlled responses; live provider generation remains to be validated.
- **Grounding verification:** `src/algolens/grounding.py` checks claims independently against approved passages. `src/algolens/nli_scorer.py` supplies a lazy-loaded NLI model adapter. Thresholds remain provisional.
- **Runtime composition:** `src/algolens/runtime.py` connects retrieval, answer generation, and grounding verification through `GroundedAnswerService`.
- **Integration coverage:** `tests/unit/test_runtime.py` tests safe abstention without evidence and lazy NLI initialization. `tests/integration/test_grounded_runtime.py` exercises the successful answer path using synthetic approved evidence and controlled test doubles.
- **Corpus limitation:** real candidate transcriptions and chunks remain pending review; tests must not change their approval status.
- **Next work:** validate live provider configuration, calibrate NLI thresholds on reviewed development examples, implement caching, and continue toward the application UI.
## Turn 5 implementation update - runtime composition (2026-10-25)

- **Provider adapter:** `src/algolens/providers.py` implements an OpenAI-compatible chat-completions adapter configurable for supported endpoints. Automated provider tests use controlled responses; a live Groq/Ollama generation success path has not yet been validated.
- **Grounding verifier:** `src/algolens/grounding.py` independently evaluates claim citations against approved passages. `src/algolens/nli_scorer.py` supplies a lazy-loaded NLI CrossEncoder adapter. The model smoke test passed its three demonstration cases, but those cases are not a lecture-corpus benchmark.
- **Runtime composition:** `src/algolens/runtime.py` now composes the retrieval pipeline, `AnswerService`, provider, and `GroundedAnswerService`. The default NLI verifier is loaded lazily; tests can inject a verifier.
- **Safety boundary:** retrieval and answer services retain eligibility checks. The current experimental corpus does not become answer-eligible, and no approval status is changed by the runtime.
- **Validation:** the complete automated quality gate passed with 209 tests; Ruff lint and format checks passed; Mypy passed for 25 source files; `uv lock --check` resolved 146 packages; `git diff --check` passed.
- **Remaining gaps:** the current runtime tests exercise safe abstention when retrieval returns no evidence. The positive answer path is integration-tested with synthetic approved evidence and fake provider/verifier components; live provider and real NLI verification remain unvalidated. Live provider behavior, NLI threshold calibration, caching, UI, deployment and final human-reviewed evaluation remain outstanding.
- **Evaluation caution:** the existing 30-question set is still draft-labelled. Provisional answerability and NLI scores must not be reported as calibrated production performance.


## GitHub checkpoint and CLI/UI completion (2026-10-26)

- **Checkpoint:** commit `fa1756d` pushed to `origin/main`; the working-tree status was clean after push.
- **CLI:** `status`, `ingest`, `index`, and `eval` are implemented. Source integrity passed for the pinned notes PDF and caption VTT. Ingestion writes derived files separately and does not change canonical chunk approval fields.
- **UI:** the Gradio app has Ask, Evidence, Trace, Evaluation, and About views. If zero child chunks have all three explicit eligibility signals, it shows safe mode and does not initialize generation.
- **Current gate results:** production index reports 0 eligible chunks and is blocked as intended. Final evaluation reports 30 draft questions, no finalized 50/30 split, no approved answer corpus, and gold IDs that do not match the approved corpus.
- **Review boundary:** pages 3–4 candidate content was compared with the official MIT PDF and the equations/partition bounds appear source-consistent. This independent source check does not substitute for project-owner approval. The existing pages 5–6 transcription remains approved but retrieval-disabled.
- **Next work:** finish source and owner review, decide retrieval eligibility separately, validate the real approved-evidence path, then complete the 80-question gold set and held-out evaluation. Deployment remains deferred.


## Evidence-bound answer cache (2026-10-26)

- **Implementation:** `src/algolens/answer_cache.py` wraps the configured provider with a local SQLite cache; the Gradio runtime uses it for generation calls.
- **Cache key:** SHA-256 covers normalized question text, ordered evidence payload, corpus version, model ID, and partial-answer mode. Updating source text or its approval fields changes the key.
- **Validity rules:** only structurally valid drafts whose cited IDs exist in the supplied approved evidence can be stored. Unapproved evidence is rejected before cache access; failed provider calls are not cached.
- **Storage policy:** the default is an OS temporary-directory SQLite file, bounded to 256 entries with a seven-day TTL. `ALGOLENS_CACHE_PATH` can override the path. Cache-write or cache-read errors fail open to a fresh provider request.
- **Tests:** added coverage for identical-request reuse, model/corpus namespace changes, evidence/partial-mode invalidation, failure behavior, approval enforcement, invalid citations, and expiration.
- **Limitations:** the cache is a performance optimization, not approval state. The canonical corpus remains retrieval-disabled and the production index/final evaluation remain blocked until their separate acceptance gates are satisfied.
