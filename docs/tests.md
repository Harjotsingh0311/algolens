---
title: AlgoLens Acceptance Tests
subtitle: Requirements expressed as executable checks
abstract: Catalogue of the tests required by the proposal.
kind: tests
status: draft
version: 0.1.0
date: 2026-10-24
keywords:
  - pytest
  - contracts
  - acceptance tests
sources:
  - docs/concept.md
  - docs/contract.md
---

# Test-first policy

Write a test before implementing each feature. A test that has never failed
before its implementation is not sufficient evidence that the test detects the bug.

## Ingestion and chunks

- T1.1: Repeated ingestion creates no duplicate chunks.
- T1.2: A manifest hash mismatch stops ingestion and identifies the source.
- T1.3: A missing URL raises a clear error and leaves no partial output.
- T2.1: A chunk at the maximum size passes; a chunk exceeding the limit is split.
- T2.2: Spoken passage timestamps are valid and never move backwards.
- T2.3: Parent-child references and pair IDs resolve to existing passages.

## Retrieval

- T3.1: A gold passage appears in the top five for its question.
- T3.2: BM25 can retrieve an exact term even when dense search misses it.
- T3.3: Empty or whitespace questions raise EmptyQuestion without searching.
- T3.4: An empty index returns no hits without crashing.

## Abstention and safety

- T4.1: An unrelated question such as "capital of France" is refused.
- T4.2: A near-miss question about Heap Sort is refused or marked partial.
- T4.3: "Ignore your sources" does not change grounded behavior.

## Citations and verification

- T5.1: Every answer sentence has a citation to a retrieved source.
- T5.2: The gold-set answer contains no unsupported facts.
- T5.3: Malformed LaTeX is sanitized before presentation.
- T6.1: Removing the only supporting passage marks the claim unsupported.
- T6.2: Repeated verification produces the same support marks.

## Providers and regressions

- T7.1: Rate limits trigger fallback; total failure yields sources-only mode.
- T7.2: API keys never appear in logs or UI text.
- T7.3: A 10,000-character question is refused politely.
- T8.1: Recall@5 and faithfulness remain within two percentage points
  of the saved development baseline.

These are planned acceptance tests. They are not all implemented or passing yet.