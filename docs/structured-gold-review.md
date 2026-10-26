# Structured gold-review decisions

The candidate bank stays immutable until a reviewer has checked the original source and
recorded an explicit decision for every question. The validator consumes a separate JSONL file:

`eval/gold/review_decisions_v1.jsonl`

Each line must contain the following fields:

```json
{
  "question_id": "GQ001",
  "decision": "approve",
  "source_checked": true,
  "reviewer": "Reviewer name",
  "reviewed_at": "2026-10-26",
  "question": "Reviewed question text?",
  "question_type": "definition_recall",
  "difficulty": "easy",
  "answerable": true,
  "key_points": ["A source-verified key point."],
  "gold_passage_ids": ["canonical-child-id"],
  "notes": "Original PDF page or video timestamp checked."
}
```

Do not copy this example as if it were a real decision. Replace each value only after checking the
original source. Create one record for every candidate ID. For an unanswerable question, set
`answerable` to `false` and leave `gold_passage_ids` empty.

Run validation with:

```powershell
uv run python -m algolens.evaluation.review_decisions
```

The command creates `eval/gold/questions_v1_reviewed.jsonl` only if all 80 decisions are present,
every decision is explicitly approved and source-checked, the split remains 50 dev / 30 test, and
every answerable question maps to production-eligible canonical passages. It rejects diagnostic-only
passages, missing reviewers/dates, duplicates, and inconsistent answerability/evidence pairs. It
never overwrites an existing output and never changes the candidate bank, canonical chunks, or
approval flags.

**Current expected behavior:** validation is blocked until real human decisions are recorded and
the canonical evidence is separately approved for retrieval and answer generation. That failure is
intentional; do not weaken these checks to produce a reviewed file prematurely.
