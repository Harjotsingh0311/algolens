# Gold question set v1 — candidate only

**Status: DRAFT. NOT A VERIFIED GOLD SET. DO NOT USE FOR FINAL BENCHMARK RESULTS.**

This is an 80-question candidate bank prepared to make review work concrete. It does not replace `questions_v0.jsonl`, and the CLI's final evaluation preflight continues to read v0 until a human-reviewed promotion is explicitly performed.

## Proposed composition

| Category | Count |
|---|---:|
| Definition / recall | 15 |
| Why / reasoning | 20 |
| Procedure / trace | 10 |
| Comparison | 10 |
| Multi-hop | 10 |
| Unanswerable (all subtypes) | 15 |
| **Total** | **80** |

## Proposed split — not frozen

- **50 dev:** GQ001–GQ050.
- **30 test:** GQ051–GQ080.
- The original 30 questions remain on dev because they already appear in provisional retrieval diagnostics. The additional 30 test candidates are newly drafted here, but this public candidate file is not a sealed holdout. Do not tune thresholds against them; freeze/review the split before final use.

## Critical review notes

- Every item is `draft_needs_human_review`. No question label was promoted.
- All gold IDs refer to experimental child chunks. They deliberately do **not** resolve to the two canonical reviewed-note child IDs, which currently remain `approved_retrieval_disabled`.
- Captions are still pending video spot-checking; PDF text/formulas must be verified against the original PDF pages. The typed-note Expectations extraction is known to have damaged math. See `review_v1_candidate.md` for per-question source locators and review checkboxes.
- The proposed ID list is only a *relevance hypothesis*. A passage must be checked for direct support, and IDs must eventually be remapped to explicit canonical chunks before a final evaluation can pass.
- This file is intentionally not consumed by `algolens.cli eval`. Final preflight remains safely blocked on v0 labels, approved corpus, and a finalized holdout.

## Schema

Rows use the v0 fields plus a proposed `split` property: `question_id`, `question`, `question_type`, `difficulty`, `answerable`, `gold_passage_ids`, `key_points`, `label_status`, `split`, and `annotation_notes`.
