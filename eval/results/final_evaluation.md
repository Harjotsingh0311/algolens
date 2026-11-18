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
The benchmark therefore uses `source_verified` labels and must not be described as a
human-reviewed or secret test set.

## Retrieval results

`question recall@5` counts an answerable question when at least one labelled passage
appears in the first five results. Fractional passage recall is reported in the JSON
artifacts as `recall@5`.

| Retriever | Overall question recall@5 | Test question recall@5 (95% bootstrap CI) | Overall MRR@10 | Test MRR@10 (95% bootstrap CI) |
|---|---:|---:|---:|---:|
| BM25 | 0.908 | **0.870** (0.739–1.000) | 0.549 | 0.451 (0.333–0.577) |
| Dense | 0.785 | 0.739 (0.565–0.913) | 0.560 | 0.482 (0.326–0.638) |
| Hybrid RRF | 0.846 | 0.739 (0.565–0.913) | 0.586 | 0.512 (0.358–0.671) |
| Hybrid + reranker | 0.877 | 0.826 (0.652–0.957) | 0.644 | **0.565** (0.417–0.717) |
| Hybrid + reranker + source pairing | **0.908** | 0.783 (0.609–0.957) | **0.650** | 0.549 (0.402–0.701) |

The proposal's 0.90 Recall@5 target is met by overall question recall for BM25 and
paired reranking. It is not met on the public test split; BM25 is strongest there at
0.870. Confidence intervals use 2,000 deterministic percentile-bootstrap samples
(seed 6046).

## Answerability and abstention

Thresholds were calibrated on the 50-question development split. Deterministic scope
guards reject prompt-injection requests, out-of-lecture topics, and unsupported exact
measurement requests before generation.

| Metric | Development | Test |
|---|---:|---:|
| AUROC | 1.000 | 1.000 |
| Coverage | 0.780 | 0.700 |
| Risk among accepted questions | 0.000 | 0.000 |
| Accuracy | 0.940 | 0.933 |
| Wrong-answer rate on unanswerable questions | 0.000 | 0.000 |
| False-refusal rate on answerable questions | 0.071 | 0.087 |
| AURC | 0.000 | 0.000 |

The retrieval-score gate accepts 21 of 23 answerable test questions (0.913), meeting
the proposal's 0.80 gate-coverage target, while accepting none of the seven
unanswerable questions. These figures evaluate the gate before generation; they must
not be confused with released-answer coverage below.

## End-to-end generation and baselines

The same 30-question public test split was run through the full application and a
no-retrieval LLM baseline. The full system includes retrieval, structured generation,
citation validation, and independent NLI verification. Only fully supported claims
are released.

| Metric | AlgoLens grounded | No-retrieval LLM |
|---|---:|---:|
| Answerable released-answer coverage | 0.783 (18/23) | 1.000 (23/23) |
| Answer rate on unanswerable questions | **0.000 (0/7)** | 1.000 (7/7) |
| Deterministic key-point recall | 0.305 | 0.562 |
| Claim support rate | 0.857 | n/a |
| Citation precision | 0.444 | n/a |
| Citation recall | 0.181 | 0.000 |
| p50 end-to-end latency | 3.01 s | 1.08 s |
| p95 end-to-end latency | 3.38 s | 1.59 s |
| Provider calls per question | 0.70 | 1.00 |
| Estimated input/output tokens per question | 844.5 / 48.0 | 121.7 / 254.8 |

The no-retrieval baseline has higher lexical coverage but answers every unanswerable
request and cannot cite the lecture. AlgoLens is safe on those requests, but its 0.783
released-answer coverage is one question short of the proposal's 0.80 target. The
verifier uses a 0.50 entailment boundary, prunes non-entailing citations, and rebuilds
partial answers from supported claims only; contradicted and weak claims are withheld.
This is a measured limitation, not a completed acceptance criterion.
Key-point recall is deterministic lexical overlap, not an independent LLM correctness
judge. Token counts are estimates when provider usage is unavailable.

The full row-level artifacts are `generation_current_test.json` and
`generation_no_retrieval_test.json`. The runner supports checkpointed provider calls
and a metrics-only refresh:

```powershell
uv run python -m tools.run_generation_evaluation --split test --mode all
uv run python -m tools.run_generation_evaluation --split test --mode all --metrics-only
```

## Ablations

The reproducible runner completed 34 configurations: 16 BM25 settings, the normal
dense retriever, context-header removal, glossary query expansion, a naive fixed-512
whitespace-token dense baseline, 12 offline RRF settings, and reranking with source
pairing off/on. Several BM25 settings tie at 0.870 test question recall@5. Full ranked
results are in `retrieval_ablations.md` and machine-readable results in
`retrieval_ablations.json`.

## Reproducibility

- Corpus SHA-256: `e52123ee972be4a6d3d89a3aad88e73678fd44b6ed01fd2a21663e1495599440`
- Question-set SHA-256: `911b694a0af5c0678192f4de0d4f38aad7a13b41f2d4ef99ad06d8a033096abf`
- Retrieval reports: `final_bm25.json`, `final_dense.json`, `final_hybrid.json`,
  `final_hybrid-reranked.json`, and `final_hybrid-reranked-paired.json`
- Ablation command: `uv run python tools/run_retrieval_ablations.py`
- Generation command: `uv run python -m tools.run_generation_evaluation --split test`

## Limitations and release blockers

- Labels were AI-assisted and need independent human review before publication as a
  human benchmark.
- The test split is version-controlled and is not a secret holdout.
- Thirty-two passages cover the proposal's randomized-Quicksort scope, not the entire
  lecture or course. The proposed 24-lecture distractor stress test was not run.
- End-to-end released-answer coverage is 0.783 (18/23), one question short of the 0.80
  proposal target. Further threshold tuning needs independent review data.
- A different-model-family correctness judge and RAGAS score were not produced. The
  available provider account did not expose a second suitable model family, so the
  report uses explicitly labelled deterministic key-point coverage instead.
- A live Hugging Face Space is not published from this environment because no Hugging
  Face account credential is configured. Raw licensed course media remains excluded.
