# AlgoLens Gold Questions v0

This initial 30-question set is a **draft**. Every row is marked
`draft_needs_human_review`; it must not be reported as a human-verified test set.

## Composition

- 5 definition / recall
- 8 why / reasoning
- 4 procedure / trace
- 4 comparison
- 4 multi-hop
- 5 unanswerable (off-topic, near-miss, out-of-corpus, prompt injection,
  and missing measurements)

## Fields

- `question_id`: stable unique ID.
- `question`: the query sent to retrieval.
- `question_type`, `difficulty`: evaluation categories.
- `answerable`: expected answerability under the current scope.
- `gold_passage_ids`: child chunk IDs considered relevant for answerable items.
  Unanswerable items intentionally have an empty list.
- `key_points`: expected content or expected refusal behavior.
- `label_status`: must change only after human review.
- `annotation_notes`: caveats for source-derived labels.

## Review protocol

1. Read the actual referenced passage, not only its preview.
2. Check every gold passage against the source page or timestamp.
3. Confirm that the question is answerable from the approved scope.
4. Check the key points and whether all necessary evidence IDs are labeled.
5. Mark an item reviewed only after it passes those checks.
6. Do not use the same test questions to tune thresholds or choose retrieval settings.

Some typed-note formulas are known to be damaged in automatic extraction.
Questions using those passages are explicitly noted and require direct PDF review.
The captions are also unverified and require video spot-checking.

A retrieval run against this file is **provisional** until the labels are reviewed.
