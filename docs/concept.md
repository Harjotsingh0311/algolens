---
title: AlgoLens Concept
subtitle: A citation-first RAG tutor for MIT 6.046J Lecture 6
abstract: A tutor that grounds each answer in lecture evidence and abstains when evidence is weak.
kind: concept
status: draft
version: 0.1.0
date: 2026-10-24
keywords:
  - RAG
  - randomized quicksort
  - citations
  - abstention
sources:
  - https://ocw.mit.edu/courses/6-046j-design-and-analysis-of-algorithms-spring-2015/resources/lecture-6-randomization-matrix-multiply-quicksort/
---

# Goal

A learner asks a question about Randomized Quicksort and receives an answer
grounded only in the approved lecture corpus, with inspectable citations.
If the evidence is insufficient, the tutor says so instead of guessing.

## People

- Learner: asks questions, inspects sources, and follows video timestamps.
- Reviewer: checks difficult questions, off-topic queries, and prompt-injection attempts.
- Maintainer: adds approved sources through the manifest.
- Out-of-scope asker: receives an abstention and the closest covered topics.

## Main objects

Source, Passage, Citation, Answer, and Gold Question.

## Rules

- R1: Every answer sentence cites at least one retrieved passage.
- R2: Citations expose the passage, lecture number, and video timestamp or notes page.
- R3: Weak evidence leads to abstention and a list of closest covered topics.
- R4: An empty index must never produce an answer from model memory.
- R5: User question text is data, not instructions that override source restrictions.
- R6: The same question and corpus version retrieve the same passages; answers are cached.
- R7: Math renders when valid; malformed LaTeX falls back to safe plain text.
- R8: Provider failures fall back to another configured model, then sources-only mode.
- R9: New sources require manifest entries and verified SHA-256 fingerprints.
- R10: API keys must never appear in logs or in user-facing output.

## Out of scope

No web search during answering, no cross-session user memory, no homework grading,
no unsupported answers from model memory, no rehosting of raw MIT videos or PDFs,
and no user-account system.

## Scope decision to verify

Lecture 6 covers both randomized algorithms for matrix multiplication and Quicksort.
Randomized Quicksort is the primary planned topic. Matrix-multiplication coverage
must be explicitly reviewed before deciding whether it is answerable.

## Completion evidence

A runnable application, source-linked answers, measured evaluation, a public repository,
automated checks, a live demo when hosting eligibility permits, and documented limitations.