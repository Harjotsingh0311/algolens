# AlgoLens Retrieval Baseline

## Current stage

The initial retrieval implementation provides a dependency-free BM25 lexical
search baseline and a tested Reciprocal Rank Fusion utility.

The current experimental corpus contains only chunks marked
`unreviewed_extraction` or `pending_spot_check`. The index therefore excludes
all current chunks by default. The `--include-unreviewed` CLI option is for
debugging only; its results carry `eligible_for_answer: false`.

## Citation handling

Each result retains its original chunk ID, parent ID, source ID, review status,
and citation locator. For PDF chunks, the locator points to PDF pages. For
caption chunks, it points to their cue-level timestamp range.

## Next steps

1. Validate retrieval against a small set of Quicksort test questions.
2. Add local dense retrieval with an embedding model.
3. Fuse dense and BM25 rankings with Reciprocal Rank Fusion.
4. Add approved-content policy and retrieval evaluation.
5. Connect retrieval to the answer-generation and citation-verification stages.

BM25 ranks lexical overlap; it is not a semantic understanding or answer-
quality metric. RRF is implemented as a reusable fusion utility but is not
yet combined with dense retrieval.
