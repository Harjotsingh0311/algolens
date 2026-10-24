# AlgoLens Chunking Pipeline

**Status:** Experimental; not approved for production retrieval.

## Inputs

The builder reads the approved source manifest and two derived artifacts:

- `corpus/experiments/pdf_extraction/notes.md`
- `corpus/processed/transcript.jsonl`

Before parsing, it verifies each underlying raw source against the SHA-256
pinned in `corpus/manifest.yaml`. It also computes a hash for each derived
artifact so the result can be tied to the exact extraction used.

## Scope filters

### Typed lecture notes

The parser uses explicit `source_page` markers to preserve PDF page
provenance. It removes repeated course headers, lecture headers, and
standalone printed page-number lines.

The scope filter retains Quicksort-related sections, including basic
Quicksort, pivot selection, randomized Quicksort, paranoid Quicksort,
and expectations.

### Timestamped captions

The transcript parser preserves cue-level start and end times. The current
scope begins at 2997.340 seconds, near the sustained Quicksort transition
identified during the initial audit.

This is a cue-level boundary, not word-level alignment and not an official
transcript verification.

## Chunk structure

The builder produces hierarchical parent and child JSONL files.

- Parent target: 480 words; configured range 400–600.
- Child target: 160 words; configured range 120–200.
- Parent records enumerate their child IDs.
- Child records carry their parent IDs.
- Both levels retain source ID, source URL, source and artifact hashes,
  licence, trust tier, scope, section context, locator, and review status.

A terminal group can be below the configured minimum when the remaining
source content is too short. Actual word counts are recorded in `report.json`.

## Observed scoped build

The inspected run produced:

- Typed notes: 2 parents, 4 children.
- Timestamped captions: 10 parents, 28 children.
- Total: 12 parents, 32 children.

These counts describe the current experiment, not an accuracy metric.

## Review status and limitations

Typed-note chunks are marked `unreviewed_extraction`.
Caption chunks are marked `pending_spot_check`.

The typed-note extraction contains known formula-layout defects. In
particular, the final Expectations parent contains diagram fragments and
damaged mathematical formatting. Repeated-header cleanup and scope filtering
do not repair these errors.

The caption track is auto-generated and still requires spot-checking against
the lecture. Neither source should be treated as fully verified merely
because its source hash was checked.

Before production retrieval, review formula-bearing chunks against the PDF,
spot-check the caption timestamps, and decide how low-confidence passages
should be excluded or trigger answer abstention.
