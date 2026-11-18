# AlgoLens proposal execution tracker

Last updated: 2026-11-18

| Proposal stage | Delivered evidence | Status |
|---|---|---|
| Repository and reproducibility | Locked uv environment, CI, Ruff, mypy, pytest, source manifest | Complete |
| Source acquisition | Video, transcript, typed notes, handwritten notes, and captions hash-pinned | Complete |
| Source review | 28 transcript-aligned caption chunks, 10 audio spot checks, 4 visually checked typed-note chunks | Complete with AI-assisted-review limitation |
| Corpus | 12 parents and 32 production-eligible child passages with page/timestamp citations | Complete for randomized Quicksort scope |
| Gold evaluation set | 80 source-verified questions; 50 dev / 30 public test; 65 answerable / 15 unanswerable | Complete with public-test and independent-review limitations |
| Retrieval | BM25, dense, RRF, cross-encoder reranking, paired sources, bootstrap CIs, 34-run ablation | Complete |
| Answerability | Development-calibrated thresholds, scope guards, AUROC and risk/coverage evaluation | Complete; 0.913 answerable gate coverage on test |
| Grounded generation | Structured provider contract, retry/cache, citation pruning, supported-only partial answers, windowed NLI, no-retrieval baseline | Implemented; 0.783 released-answer coverage is one question short of target |
| User interface | Ask, Evidence, Trace, live Evaluation dashboard, Algorithm Lab, health/readiness probes | Complete locally |
| Algorithm Lab | Seeded randomized Quicksort, comparisons, traces, repeated trials | Complete |
| Hosted release | Hugging Face-compatible repository metadata and app entry point | Blocked on account login, secret, and live deployment |

## Acceptance results

- Production corpus: 32/32 child passages eligible.
- Source integrity: 5/5 sources verified; no pending or unhashed sources.
- Paired reranking overall question recall@5: 0.908.
- Best public-test question recall@5: 0.870 (BM25).
- Public-test answerability accuracy: 0.933.
- Public-test wrong-answer rate on unanswerable questions: 0.000.
- Public-test answerable acceptance: 21 of 23 answerable questions (0.913).
- End-to-end released-answer coverage: 18 of 23 answerable questions (0.783).
- End-to-end unanswerable answer rate: 0 of 7 (0.000); no-retrieval baseline: 7 of 7 (1.000).

## Honest boundaries

The proposal's 0.90 retrieval target is met overall, not on the public test split.
The project owner authorized an AI-assisted source review; it must not be described as
independent human annotation. The checked-in test split is useful for reproducibility
but is not secret. The 24-lecture stress test, different-family correctness judge,
independent human sign-off, and live Hugging Face deployment remain incomplete. Actual
hosting is an account-level operation because the service needs private credentials.

Detailed results and reproduction commands are in
[`eval/results/final_evaluation.md`](../eval/results/final_evaluation.md).
