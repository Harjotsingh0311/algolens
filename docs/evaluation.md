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


## Answerability and abstention metrics

The standalone runner evaluates supplied scores against the **separately human-reviewed**
`eval/gold/questions_v1_reviewed.jsonl` file. It refuses candidate/draft labels and requires
one unique score row for every gold question ID.

Prepare a score file (one JSON object per line) containing the question ID and the score produced
by the model or gate being evaluated:

```json
{"question_id":"GQ001","score":1.42}
{"question_id":"GQ002","score":null}
```

Then run:

```powershell
uv run python -m algolens.evaluation.answerability_runner --scores eval/results/answerability_scores.jsonl --answer-threshold 1.0 --partial-threshold 0.0
```

A numeric score at or above the answer threshold becomes `answer`; a score between thresholds
becomes `partial`; lower or missing scores become `abstain`. The report includes coverage, risk,
false-refusal rate, wrong-answer rate on unanswerable questions, and a risk-coverage curve/AURC.

This command **does not generate scores or calibrate thresholds**. Use the development split for
threshold selection and report final results on the held-out test split separately. Until the gold
set is genuinely reviewed and the canonical evidence gate is satisfied, no final performance claim
is justified.
