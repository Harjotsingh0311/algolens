# AlgoLens Retrieval Comparison — Draft v0

> **Provisional diagnostic only.** Labels and corpus passages still require human verification. Do not present this as final performance.

## Experimental consistency

- Answerable questions scored: 25
- Unanswerable questions excluded from retrieval ranking metrics: 5
- Question-set SHA-256: `061aa4805330d4799280939379e664bb1db10aae770346135687b94e39a8746e`
- Corpus SHA-256: `3e08079e6eca9f60a5c14e8b4a00d35607209c4aec2d7d292401a10d21d2ad1a`
- All three reports passed the hash consistency checks.

## Aggregate metrics

| Metric | BM25 | Dense | Hybrid RRF | Best observed |
|---|---:|---:|---:|---|
| recall@1 | 0.2400 | 0.2200 | 0.2633 | Hybrid RRF |
| recall@3 | 0.5033 | 0.4100 | 0.5467 | Hybrid RRF |
| recall@5 | 0.6500 | 0.4433 | 0.6333 | BM25 |
| recall@10 | 0.8433 | 0.6333 | 0.8000 | BM25 |
| mrr@10 | 0.7253 | 0.5935 | 0.6924 | BM25 |
| ndcg@10 | 0.6599 | 0.5197 | 0.6462 | BM25 |

## Delta relative to BM25

Positive values mean the other retriever scored higher on that metric.

| Metric | Dense − BM25 | Hybrid RRF − BM25 |
|---|---:|---:|
| recall@1 | -0.0200 | +0.0233 |
| recall@3 | -0.0933 | +0.0433 |
| recall@5 | -0.2067 | -0.0167 |
| recall@10 | -0.2100 | -0.0433 |
| mrr@10 | -0.1318 | -0.0329 |
| ndcg@10 | -0.1402 | -0.0137 |

## Provisional interpretation

- Keep BM25 as the initial retrieval baseline: it has the highest observed Recall@5, Recall@10, MRR@10, and nDCG@10.
- Keep Hybrid RRF for follow-up experiments: it has the highest observed Recall@1 and Recall@3.
- Dense-only retrieval scored below the other methods on these draft labels in this run.
- These observations are limited to this small, unreviewed corpus and draft question set. They do not establish general superiority.
- The current evaluation does not measure answer correctness, faithfulness, citation quality, abstention, latency, or reranking.

## Metric definitions

- **Recall@k:** fraction of labeled relevant passages retrieved in the first k results, averaged over answerable questions.
- **MRR@10:** average reciprocal rank of the first relevant passage within the top 10.
- **nDCG@10:** ranking quality with binary passage relevance.

Unanswerable questions are counted, not scored by these retrieval metrics. Abstention needs a separate evaluation.
