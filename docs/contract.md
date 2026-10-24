---
title: AlgoLens Contract
subtitle: Stable data models and component boundaries
abstract: Defines the source, passage, retrieval, claim, and answer interfaces.
kind: contract
status: draft
version: 0.1.0
date: 2026-10-24
keywords:
  - contracts
  - pydantic
  - passages
sources:
  - docs/concept.md
---

# Purpose

This document mirrors the initial contract in the project proposal. It describes
required behavior; implementation details may be added without silently changing
released interfaces.

## Passage

Required fields:

- `id: str`
- `lecture: int`
- `kind: spoken | notes | handwritten`
- `text: str`
- `t_start: float | None`
- `t_end: float | None`
- `page: int | None`
- `section: str`
- `parent_id: str | None`
- `pair_id: str | None`

For spoken passages, start and end timestamps must be valid and ordered.
For notes passages, page metadata must be retained when available.

## Hit

- `passage`: a Passage
- `score`: numeric reranking score
- `ranks`: retrieval positions, including BM25 and dense retrieval ranks where available

## Claim

- `text`: one answer claim
- `cites`: passage IDs
- `support`: `supported`, `weak`, `unsupported`, or null before verification

Every cited ID must be present in the answer's retrieved sources.

## Answer

- `status`: `answered`, `partial`, `abstained`, or `sources_only`
- `answer_md`: rendered answer or abstention message
- `claims`: claim-level citation records
- `sources`: retrieved evidence
- `closest_topics`: nearest covered topics for abstentions and partial answers
- `corpus_version`: identity of the indexed corpus
- `model`: model/provider identifier
- `latency_ms`: elapsed time

## Public operations

- `retrieve(question, k=6)`: returns ranked evidence or raises EmptyQuestion.
- `decide(hits)`: returns answer, partial, or abstain.
- `answer(question)`: returns an Answer and handles provider errors safely.

The UI and evaluation must depend on this public answer contract, not private functions.
A released contract version is extended alongside the old version rather than changed in place.