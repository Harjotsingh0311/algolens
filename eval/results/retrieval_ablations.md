# AlgoLens retrieval ablations

Corpus SHA-256: `e52123ee972be4a6d3d89a3aad88e73678fd44b6ed01fd2a21663e1495599440`

Question set SHA-256: `911b694a0af5c0678192f4de0d4f38aad7a13b41f2d4ef99ad06d8a033096abf`
Completed runs: **34**

`question_recall@5` counts a question when at least one labelled passage appears in the first five results. `fractional_recall@5` averages the fraction of all labelled passages recovered for each question.

| Run | Test question recall@5 | Test fractional recall@5 | Test MRR@10 | Overall question recall@5 |
|---|---:|---:|---:|---:|
| naive-fixed-512-dense | 0.957 | 0.714 | 0.708 | 0.985 |
| bm25-k1-2.0-b-0.25 | 0.870 | 0.481 | 0.479 | 0.892 |
| bm25-k1-1.5-b-0.5 | 0.870 | 0.481 | 0.461 | 0.908 |
| bm25-k1-2.0-b-0.5 | 0.870 | 0.481 | 0.457 | 0.892 |
| bm25-k1-2.0-b-0.75 | 0.870 | 0.481 | 0.453 | 0.908 |
| bm25-k1-1.2-b-0.5 | 0.870 | 0.481 | 0.451 | 0.908 |
| bm25-k1-1.5-b-0.25 | 0.870 | 0.481 | 0.451 | 0.892 |
| bm25-k1-1.5-b-0.75 | 0.870 | 0.481 | 0.451 | 0.908 |
| bm25-k1-1.2-b-0.75 | 0.870 | 0.481 | 0.448 | 0.908 |
| bm25-k1-1.2-b-1.0 | 0.870 | 0.496 | 0.440 | 0.908 |
| bm25-k1-0.8-b-0.75 | 0.870 | 0.496 | 0.438 | 0.892 |
| bm25-k1-0.8-b-1.0 | 0.870 | 0.517 | 0.433 | 0.892 |
| bm25-k1-2.0-b-1.0 | 0.870 | 0.481 | 0.432 | 0.908 |
| bm25-k1-1.5-b-1.0 | 0.870 | 0.481 | 0.422 | 0.908 |
| hybrid-reranked | 0.826 | 0.478 | 0.565 | 0.877 |
| bm25-k1-1.2-b-0.25 | 0.826 | 0.467 | 0.440 | 0.877 |
| bm25-k1-0.8-b-0.25 | 0.826 | 0.481 | 0.433 | 0.877 |
| bm25-k1-0.8-b-0.5 | 0.826 | 0.496 | 0.433 | 0.877 |
| hybrid-reranked-paired | 0.783 | 0.422 | 0.549 | 0.908 |
| hybrid-rrf-30-candidates-30 | 0.739 | 0.467 | 0.517 | 0.846 |
| hybrid-rrf-60-candidates-30 | 0.739 | 0.467 | 0.517 | 0.846 |
| hybrid-rrf-100-candidates-30 | 0.739 | 0.467 | 0.516 | 0.846 |
| hybrid-rrf-10-candidates-30 | 0.739 | 0.489 | 0.515 | 0.862 |
| hybrid-rrf-30-candidates-20 | 0.739 | 0.467 | 0.512 | 0.846 |
| hybrid-rrf-60-candidates-20 | 0.739 | 0.467 | 0.512 | 0.846 |
| hybrid-rrf-100-candidates-20 | 0.739 | 0.467 | 0.512 | 0.846 |
| hybrid-rrf-10-candidates-20 | 0.739 | 0.489 | 0.510 | 0.862 |
| dense-default | 0.739 | 0.428 | 0.482 | 0.785 |
| dense-context-headers-off | 0.739 | 0.429 | 0.438 | 0.800 |
| dense-query-expansion-glossary | 0.696 | 0.304 | 0.523 | 0.708 |
| hybrid-rrf-100-candidates-10 | 0.696 | 0.420 | 0.515 | 0.815 |
| hybrid-rrf-30-candidates-10 | 0.696 | 0.420 | 0.515 | 0.815 |
| hybrid-rrf-60-candidates-10 | 0.696 | 0.420 | 0.515 | 0.815 |
| hybrid-rrf-10-candidates-10 | 0.696 | 0.420 | 0.513 | 0.815 |

The saved test split is version-controlled, so it is a held-out workflow split rather than a secret benchmark. Question labels received AI-assisted source review and should be independently reviewed before making a stronger claim.
