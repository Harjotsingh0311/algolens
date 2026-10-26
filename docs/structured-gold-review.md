# Structured gold-review decisions

The candidate bank stays immutable until a reviewer has checked the original source and
recorded an explicit decision for every question. The validator consumes a separate JSONL file:

`eval/gold/review_decisions_v1.jsonl`

Create the blank template first:

```powershell
uv run python -m algolens.evaluation.review_decisions --write-template
```

The template leaves every decision pending, sets `source_checked` to false, and separates the
candidate passage IDs into `proposed_gold_passage_ids`. Review each question against its original
source and fill in the final `gold_passage_ids` yourself. The command refuses to overwrite an
existing decision file.

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
every decision is explicitly approved and source-checked, the split remains 50 dev / 30 test, the
proposal's question-type counts are preserved, and exactly 65 questions are answerable while 15 are
unanswerable. Every answerable question must map to production-eligible canonical passages. It
rejects diagnostic-only passages, missing reviewers/dates, duplicates, and inconsistent
answerability/type/evidence pairs. It never overwrites an existing output and never changes the
candidate bank, canonical chunks, or approval flags.

**Current expected behavior:** validation is blocked until real human decisions are recorded and
the canonical evidence is separately approved for retrieval and answer generation. That failure is
intentional; do not weaken these checks to produce a reviewed file prematurely.

## Protecting review artifacts

The review-packet generator now refuses to replace an existing output file by default. This protects annotations or reviewer edits made after an earlier packet was generated.

Generate a fresh packet at a new path:

```powershell
uv run python -m algolens.evaluation.review_packet --output eval/results/gold_review_packet_round2.md
```

Only pass `--force` after inspecting the existing file and deciding that replacement is intended:

```powershell
uv run python -m algolens.evaluation.review_packet --force
```

This safeguard affects only the generated Markdown packet. It does not approve any questions or passages, and it does not change candidate labels, canonical chunks, or eligibility flags.


## Prioritized source-review queue

The gold-candidate audit JSON now includes `review_queue`, `review_queue_count`, and
`review_queue_priority_counts`. The queue is a triage aid, not a decision record:

- **P0:** evidence mapping needs attention first (unknown IDs, diagnostic-only IDs, or missing
  proposed evidence for a question not labelled unanswerable).
- **P1:** human review is pending or the wording/type heuristic raised an advisory flag, without
  one of the P0 evidence blockers.
- Each entry includes the question ID, split, reasons, candidate passage IDs, canonical IDs,
  diagnostic-only IDs, unknown IDs, and any advisory wording/type flags.

Generate the audit as usual with `uv run python -m algolens.evaluation.gold_audit`. This queue
does not modify the candidate JSONL, approve passages, mark a question reviewed, or permit final
evaluation. A reviewer must still check original lecture sources and record explicit decisions.
