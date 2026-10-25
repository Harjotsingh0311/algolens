# Gold-Label Recommendations v0

**Status:** Recommendations only. The canonical `gold_passage_ids` and current
key points have not been changed. GQ023 and GQ025 remain
`draft_needs_human_review`.

## GQ023 - Median-pivot recurrence

The user reports that the video confirms the recurrence, the two linear terms,
the worst-case conclusion, and the caption timestamp alignment.

### Recommended gold passage IDs

**Retain:**
- `L06_YOUTUBE_CAPTIONS-parent-0005-child-0002`
- `L06_TYPED_NOTES-parent-0001-child-0002`

**Recommend removing as redundant:**
- `L06_YOUTUBE_CAPTIONS-parent-0005-child-0003`

The second caption child mainly discusses practical performance and the
asymptotic-versus-practical distinction. The preceding child directly contains
the median-based recurrence, both `Θ(n)` terms, and the worst-case
`Θ(n log n)` conclusion required by this question. The removal is a
recommendation, not yet applied to the canonical label.

### Recommended key points

1. Median-based pivoting creates two half-sized recursive subproblems.
2. The recurrence includes two recursive calls and separate `Θ(n)`
   work for median selection and partitioning.
3. The recurrence solves to worst-case `Θ(n log n)` time.

## GQ025 - Expected-time recursion-tree analysis

The user reports that the video confirms the tree analysis, final expected
`Θ(n log n)` conclusion, and caption timestamp alignment.

### Recommended gold passage IDs

Retain the current four IDs for now:

- `L06_YOUTUBE_CAPTIONS-parent-0009-child-0001`
- `L06_YOUTUBE_CAPTIONS-parent-0009-child-0002`
- `L06_YOUTUBE_CAPTIONS-parent-0010-child-0001`
- `L06_TYPED_NOTES-parent-0002-child-0001`

The three caption chunks cover the work-tree explanation, tree height, work
per level, and final bound. The typed-notes chunk points to the requested
Expectations section, but its extracted formula is damaged. Keep the extraction
caveat; do not make this chunk answer-eligible until a corrected, reviewed
version is available.

### Recommended key points

1. The typed notes bound expected work by
   `T(n) ≤ T(n/4) + T(3n/4) + 2cn`.
2. The largest branch shrinks by a factor of at most `3/4`, giving
   logarithmic recursion-tree height.
3. The lecture's tree analysis has linear total work per level.
4. Combining linear work per level with logarithmic height gives expected
   `Θ(n log n)` running time.

The good-pivot probability and expected-retry bound are already the central
focus of GQ024. Keeping them out of GQ025's primary key points reduces
unnecessary duplication while retaining the recurrence needed for the tree
argument.

## Safeguards

- No canonical gold-passage IDs were changed by this recommendation.
- No question was promoted to a verified label.
- The video evidence is recorded as user-reported, not independently checked
  by the assistant.
- Reassess recommendations after the corrected typed-notes chunk is available
  and the full gold-label review is complete.
