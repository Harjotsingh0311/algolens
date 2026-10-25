# Retrieval Evaluation: v0

AlgoLens uses a 30-question draft set for its first retrieval measurements.

Run `tools/evaluate_retrieval.py` with `--retriever bm25`, `dense`, or
`hybrid-rff`. The current labels are drafts, so evaluations must explicitly
pass `--allow-draft-labels`; reports are marked provisional.

Metrics:
- Recall@1/3/5/10: fraction of labeled relevant passages recovered.
- MRR@10: reciprocal rank of the first relevant passage within the top 10.
- nDCG@10: ranking quality with binary relevance.
- By-type metrics: diagnostic breakdown across question categories.

Unanswerable questions are counted but excluded from retrieval relevance
metrics. They do not measure abstention. Abstention requires an answerability
gate and its own held-out evaluation.

The corpus contains content that is still unreviewed. These metrics measure
retrieval against provisional labels and must not be reported as final
project performance.
