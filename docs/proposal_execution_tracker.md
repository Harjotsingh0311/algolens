# AlgoLens - Proposal Execution Tracker

Last updated: 2026-10-25
Project: MIT 6.046J Lecture 6 citation-first RAG tutor
Purpose: Track proposal requirements beside implementation evidence.

## Proposal workstreams side by side

| Proposal stage | Requirement | Current evidence | Status | Next acceptance gate |
|---|---|---|---|---|
| Turn 0 | Repository, concept, manifest, developer tooling, CI and deployment eligibility | Project scaffold, manifest, tests and developer tooling exist. | Mostly complete | Verify current Hugging Face/ZeroGPU eligibility. |
| Turn 1 | Fetch and parse notes/transcript; validate locators | Typed-notes PDF is hash-pinned; captions are parsed into timestamped JSONL; extraction comparisons exist. | In progress | Finish source audit and caption-alignment review. |
| Turn 2 | Baseline, 30-question gold set and evaluation harness | BM25, dense and RRF evaluation reports exist; 30-question gold set is draft-labelled. | Implemented, provisional | Human-review labels; finalize dev/test split and final reports. |
| Turn 3 | Teach-unit chunks, hybrid retrieval, RRF, reranking, context headers and ablations | Experimental chunks and retrieval baselines exist; reviewed pages 5-6 have separate provenance-preserving chunks; HybridIndex fuses BM25/dense rankings with RRF; CrossEncoderReranker is implemented and unit tested. | In progress | Connect reranking to the runtime query flow, then run ablations and compare retrieval quality. |
| Turn 4 | Answerability gate, abstention and risk-coverage evaluation | Retrieval eligibility allowlist exists; full abstention system is not complete. | Pending | Implement and evaluate risk-coverage, false refusals and wrong-answer risk. |
| Turn 5 | Generation contract, grounded citations, claim verification, model adapter and cache | Some contracts and documentation exist; complete grounded generation pipeline is not implemented. | Pending | Implement answer generation, citation verification and Groq/Ollama adapter/cache. |
| Turn 6 | Gradio UI, live deployment, probes and operational documentation | Developer documentation and tests exist; application UI and deployment remain outstanding. | Pending | Build UI, deploy, add health probes and validate a live demo. |
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
| Final project quality gate | Full test suite, lint, formatting, type, lockfile and whitespace checks | 91 tests passed after the reranker addition; Ruff lint and formatting checked; Mypy, UV lock and Git whitespace checks recorded from this run | Verified 2026-10-25 |
| Runtime hybrid retrieval | HybridIndex fuses BM25 and dense rankings with RRF; 8 focused tests passed. | Implemented as a reusable component; application query-flow integration remains |
| Cross-encoder reranking | Separate CrossEncoderReranker component; lazy optional model loading, finite-score checks, citation preservation and eligibility gate; 10 focused tests passed. | Implemented as a component; runtime query-flow integration remains |
| Abstention, grounded generation, UI and deployment | Not fully implemented | Pending |

## Evaluation interpretation

Recorded Recall@k, MRR and nDCG results are provisional diagnostics because the gold labels have not all been human-reviewed. They must not be reported as final benchmark results.

The captions are auto-generated and are not independently verified against the video. The reviewed typed-notes transcription covers only printed pages 5-6; it does not approve the full PDF extraction or caption corpus.

## Immediate next gates

1. Review the final Git diff and commit this isolated reviewed-source integration.
2. Keep retrieval eligibility disabled until the retrieval integration gate is separately tested and approved.
3. Implement runtime hybrid retrieval, reranking and ablations.
4. Implement abstention, grounded generation, citation verification and caching.
5. Build the UI and deployment probes.
6. Complete the final human-reviewed evaluation and proposal acceptance checklist.
