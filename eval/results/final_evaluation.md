# AlgoLens final evaluation

Evaluation date: 2026-11-18

Scope: MIT 6.046J Spring 2015, Lecture 6 randomized Quicksort

Corpus: 32 approved child passages

Question set: 80 source-verified questions (50 development, 30 public test)

## Evidence and label status

All production passages are backed by hash-pinned MIT OCW material. The 28 caption
passages were aligned to the official transcript and ten timestamps were spot-checked
against lecture audio. Four typed-note passages were checked against the rendered PDF.
The project owner authorized promotion on 2026-11-18.

This was an AI-assisted source review, not an independent human annotation exercise.
The benchmark therefore uses `source_verified` labels and should not be described as a
human-reviewed or secret test set.

## Retrieval results

`question recall@5` counts an answerable question when at least one labelled passage
appears in the first five results. Fractional passage recall is reported in the JSON
artifacts as `recall@5`.

| Retriever | Overall question recall@5 | Test question recall@5 | Overall MRR@10 | Test MRR@10 |
|---|---:|---:|---:|---:|
| BM25 | 0.908 | **0.870** | 0.549 | 0.451 |
| Dense | 0.785 | 0.739 | 0.560 | 0.482 |
| Hybrid RRF | 0.846 | 0.739 | 0.586 | 0.512 |
| Hybrid + reranker | 0.877 | 0.826 | 0.644 | **0.565** |
| Hybrid + reranker + source pairing | **0.908** | 0.783 | **0.650** | 0.549 |

The proposal's 0.90 Recall@5 target is met by overall question recall for BM25 and
paired reranking. It is not met on the public test split; BM25 is strongest there at
0.870. Pairing improves overall multi-source coverage and MRR but reduces test
question recall compared with unpaired reranking.

## Answerability and abstention

Thresholds were calibrated on the 50-question development split. Deterministic scope
guards reject prompt-injection requests, out-of-lecture topics, and unsupported exact
measurement requests before generation.

| Metric | Development | Test |
|---|---:|---:|
| Coverage | 0.780 | 0.700 |
| Risk among accepted questions | 0.000 | 0.000 |
| Accuracy | 0.940 | 0.933 |
| Wrong-answer rate on unanswerable questions | 0.000 | 0.000 |
| False-refusal rate on answerable questions | 0.071 | 0.087 |
| AURC | 0.000 | 0.000 |

The test result meets both the proposal's wrong-answer-rate target and its 80%
answerable-coverage target: 21 of 23 answerable questions were accepted (0.913).
Overall decision coverage is 0.700 because correct abstentions on unanswerable
questions are not accepted. Partial answers count as accepted in these metrics.

## Ablations

The reproducible ablation runner completed 31 configurations: 16 BM25 settings, one
dense baseline, 12 offline RRF configurations, and reranking with pairing off/on.
Several BM25 settings tie at 0.870 test question recall@5. Full ranked results are in
`retrieval_ablations.md` and machine-readable results in `retrieval_ablations.json`.

## Live grounded-answer smoke test

A live Groq request using `openai/gpt-oss-120b` answered the expected-runtime recurrence
question from six approved retrieved passages. The generated atomic claim cited
`L06_TYPED_NOTES-parent-0002-child-0001`; the independent NLI verifier marked it
supported before release. A prior composite draft was withheld, demonstrating the
fail-closed path.

This is a smoke test, not a statistically powered generated-answer evaluation.

## Reproducibility

- Corpus SHA-256: `e52123ee972be4a6d3d89a3aad88e73678fd44b6ed01fd2a21663e1495599440`
- Question-set SHA-256: `7f5480c49e1d09085b30ffb2c0bede3cc7abdbf8a0d5fc3128df7c6f14f9748d`
- Final reports: `final_bm25.json`, `final_dense.json`, `final_hybrid.json`,
  `final_hybrid-reranked.json`, and `final_hybrid-reranked-paired.json`
- Ablation command: `uv run python tools/run_retrieval_ablations.py`

## Limitations

- Labels were AI-assisted and should receive independent review before publication as a
  human benchmark.
- The test split is version-controlled and is not a secret holdout.
- Thirty-two passages cover the proposal's randomized-Quicksort scope, not the entire
  lecture or course.
- Retrieval and answerability metrics do not establish pedagogy, style, or factual
  correctness of every possible generated response.
- Live deployment still requires the host account to configure `GROQ_API_KEY` as a
  secret; raw licensed course media remains intentionally excluded from Git.
