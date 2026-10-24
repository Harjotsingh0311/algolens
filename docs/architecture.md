---
title: AlgoLens Architecture
subtitle: Offline indexing and online answering
abstract: The direction of data flow through AlgoLens.
kind: architecture
status: draft
version: 0.1.0
date: 2026-10-24
keywords:
  - ingestion
  - retrieval
  - generation
sources:
  - docs/concept.md
---

# Offline pipeline

Manifest and source checks
-> PDF/transcript extraction
-> transcript time alignment
-> parent-child teach-unit chunking
-> context headers and glossary
-> dense embeddings and BM25 index.

# Online pipeline

Question validation and glossary expansion
-> hybrid BM25+dense retrieval
-> reciprocal rank fusion
-> cross-encoder reranking
-> answer/partial/abstain gate
-> cited generation
-> independent claim verification
-> evidence and trace presentation.

# Module boundaries

The intended direction is:

`ingest -> chunking -> indexing -> retrieval -> gate -> generation -> verify -> app`

The application is a thin caller of the public interfaces. Secrets remain in environment
configuration or hosting secrets. Raw downloads are not committed to Git.