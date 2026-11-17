# Proposal gap audit — 2026-10-27

This audit maps the AlgoLens proposal (v0.1.0, dated 2026-10-23) to the repository at main commit `92dd49f263cb5ac91ab5ee1e475247557f7c9e05`. It distinguishes implementation from acceptance evidence. Passing unit tests is not a benchmark, and candidate material is not approved source evidence.

## Executive result

**Status: implementation foundation is strong; proposal acceptance is blocked by source review, retrieval eligibility, and final evaluation.** The app intentionally remains in safe mode. Do not unlock generation merely to make the demo answer.

## Requirement-by-requirement

| Proposal requirement | Audit finding | Status / next action |
|---|---|---|
| Concept, manifest, contracts, docs, dev tooling | Present: `docs/concept.md`, `docs/contract.md`, `docs/tests.md`, `corpus/manifest.yaml`, Makefile, pyproject, lockfile, CI | Implemented; confirm naming/writing handbook requirements before release |
| Source fingerprinting and ingestion | Manifest/hash validation, PDF extraction, VTT caption conversion and source-aware JSONL exist | Partial: video/caption alignment and full notes formula review remain |
| Timestamped lecture transcript | Timestamped caption-derived JSONL exists | Partial: captions are not independently spot-checked against the video; proposal asks for 10 timestamp spot checks |
| Teach-unit parent/child chunks | Chunking tools and experiment/review candidate outputs exist | Partial: source-specific boundaries/content must be reviewed and accepted |
| Two-voice spoken+notes pairing (N2) | Not evidenced as complete in runtime corpus | Missing: implement after source approval; measure multi-hop Recall@5 with/without pairing |
| BM25 + dense + RRF + cross-encoder rerank | Components, pipeline, tests, and diagnostics exist | Code implemented; production retrieval remains locked until eligible canonical children exist; systematic ablation is open |
| Measured abstention gate (N1) | Gate and risk/coverage metric code exist; draft-set diagnostic exists | Partial: diagnostic output is not calibrated; review labels, tune only on dev, evaluate held-out once |
| Claim-level verification (N3) | Structured claims and NLI verifier exist with tests | Partial: thresholds not calibrated against human-labeled claims; independent verification results are not final |
| Structured citation generation, fallback, cache | Answer contracts, citations, provider adapter/fallback, sources-only degradation, SQLite cache exist | Code implemented; live provider/rate-limit smoke and corpus-backed positive path remain to be accepted |
| Algorithm Lab (N5) | Seeded Quicksort CLI, comparison counters, traces, repeated trials, and Gradio tab exist | Implemented; still needs report artifact/automated empirical plot against the expected ~1.39 n log2 n comparison trend, interpreted as finite-trial evidence |
| Gold set of 80 with 50/30 split (N4) | An 80-item candidate bank and audit/review tooling exist | Blocked: every item remains unreviewed; gold IDs are diagnostic/non-canonical; the public candidate split is not a sealed held-out test |
| ~30 controlled ablations (N4) | Some exploratory retrieval/gate reports and comparison tools exist | Missing as a reproducible, systematic report; run only after gold and corpus approvals |
| 24-lecture distractor stress test (N6) | No evidence that full 24-lecture evaluation corpus and run are complete | Missing/stretch; only run when sources and tier separation are sound |
| Live Hugging Face Space | App metadata is in README and local Gradio app exists | Not accepted/deployed based on repo evidence; deploy only after corpus/evaluation gates and HF eligibility check |
| CI and release | Main CI has a recent green report (269 tests as of 2026-10-26); no release workflow visible in tree; Makefile release remains a placeholder | CI implemented; tag/release publishing and deployment probes are not complete |
| Licence/attribution | MIT code licence and content licence note exist | Verify each source’s licence and derivative redistribution before releasing processed corpus |

## Critical blockers (do not bypass)

1. **Canonical source evidence:** no canonical child passage has all required approval signals (`review_status`, `eligible_for_answer: true`, and `retrieval_eligible: true`). The UI should continue to abstain.
2. **Source verification:** captions need spot-checking against the actual lecture, and the typed-note formula flagged in `corpus/processed/notes_formula_review.md` needs direct PDF review. Pages 5–6 have partial review; this is not blanket approval of the whole transcript or notes.
3. **Gold set integrity:** complete human decisions in `eval/gold/review_decisions_v1.jsonl`; the validator should be the gatekeeper. Do not treat the candidate JSONL as reviewed, do not promote diagnostic-only IDs, and do not claim held-out scores from a visible/test candidate.
4. **Evaluation protocol:** only after 1–3, establish a defensible split, tune the gate on development questions, freeze settings, run test once, and report confidence intervals plus baselines/ablations.
5. **Deployment:** do not call it production-ready until approved evidence, a positive corpus-backed integration test, the final report, and live probes pass.

## Recommended execution order

### Gate A — evidence readiness
- [ ] Verify caption timestamps at 10 randomly selected positions in the video; record sample time, caption text, and observed alignment.
- [ ] Review the suspect equation in the original typed-notes PDF and record the page, correct transcription, reviewer, and date.
- [ ] Review each candidate parent/child passage against the source, correcting formulas and citations.
- [ ] Make explicit, separate decisions for source review and answer/retrieval eligibility. Use the repository's existing review schema and commands.
- [ ] Re-run source integrity, candidate audit, and corpus readiness.

### Gate B — evaluation readiness
- [ ] Review all 80 questions and key points against source evidence.
- [ ] Map every answerable question to approved canonical child passage IDs; unanswerable rows have no gold IDs.
- [ ] Freeze the intended 50 development / 30 test assignments in an artifact that records provenance and cannot be silently regenerated.
- [ ] Run baseline (no retrieval), naive dense-only RAG, BM25-only, hybrid RRF, and reranked hybrid.
- [ ] Run the planned one-factor ablations; keep config, seed, corpus hash, model versions, and result JSON for every run.
- [ ] Calibrate abstention and claim verification on development labels; run final held-out metrics once with 95% confidence intervals.

### Gate C — proposal differentiators
- [ ] Implement and measure transcript↔notes pairing, with and without pairing on multi-hop Recall@5.
- [ ] Add a reproducible Quicksort empirical plot and test; distinguish a finite sample from a mathematical guarantee.
- [ ] Run the 24-lecture distractor test as a separate evaluation-only corpus, never as deployed answer evidence.
- [ ] Fill the Evaluation tab with the *actual committed report* and clearly label diagnostic versus final results.

### Gate D — release
- [ ] Validate local server `/healthz` and `/readyz`; current safe-mode `/readyz=503` is expected.
- [ ] Confirm HF ZeroGPU eligibility / allowed SDK and store API keys as Space Secrets.
- [ ] Deploy the approved version, run live positive/negative/injection/provider outage probes, and record results.
- [ ] Add a version tag and release workflow only when quality gates pass; publish results and known limits in README.

## Evidence standard

Each checked box should point to one of: a source-review record, a committed artifact/report, an automated test and CI run, or a live probe record. “File exists”, “unit tests pass”, a model smoke query, and an exploratory number are not substitutes for the proposal’s acceptance criteria.

## Audit references

- Proposal: Sections 4–7 (concept, corpus, pipeline); 9–13 (contract, tests, evaluation, tools and deployment); 14–18 (roadmap, risks, interview, deliverables).
- Current repository status summary: `README.md` and `docs/proposal_execution_tracker.md`.
- Candidate review process: `docs/structured-gold-review.md`.
- Caption review utilities: `tools/audit_captions.py`.
- Existing source formula review: `corpus/processed/notes_formula_review.md`.
