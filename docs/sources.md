---
title: AlgoLens Sources and Attribution
subtitle: Approved source locations and integrity policy
abstract: Identifies the official MIT OpenCourseWare resources used by the corpus.
kind: sources
status: draft
version: 0.1.0
date: 2026-10-24
keywords:
  - MIT OCW
  - attribution
  - SHA-256
sources:
  - https://ocw.mit.edu/courses/6-046j-design-and-analysis-of-algorithms-spring-2015/resources/lecture-6-randomization-matrix-multiply-quicksort/
---

# Primary material

Course: MIT 6.046J Design and Analysis of Algorithms, Spring 2015.

Lecture: Lecture 6, "Randomization: Matrix Multiply, Quicksort".
Instructor for this lecture: Srinivas Devadas.

- Lecture resource page:
  https://ocw.mit.edu/courses/6-046j-design-and-analysis-of-algorithms-spring-2015/resources/lecture-6-randomization-matrix-multiply-quicksort/
- Video download:
  https://archive.org/download/MIT6.046JS15/MIT6_046JS15_lec06_300k.mp4
- Typed notes:
  https://ocw.mit.edu/courses/6-046j-design-and-analysis-of-algorithms-spring-2015/cb55cb123a557eed0738a1187a452c24_MIT6_046JS15_lec06.pdf
- Handwritten notes:
  https://ocw.mit.edu/courses/6-046j-design-and-analysis-of-algorithms-spring-2015/7d59cd5e4d6cb323739deff687ed1bff_MIT6_046JS15_writtenlec6.pdf

The lecture page provides a transcript interface. Its exact extraction route and timestamp
availability must be verified during ingestion; do not assume the transcript is timestamped.

# Integrity policy

Each source belongs in `corpus/manifest.yaml`. The initial SHA-256 fields are null because
the actual assets have not been downloaded and verified. Ingestion must not accept a null
hash as a verified fingerprint. Pin the calculated SHA-256 before indexing a source.

# Licensing and handling

The proposal specifies Creative Commons BY-NC-SA 4.0 for course materials. Preserve
MIT attribution, link users to the original source, and keep raw videos and PDFs out of Git.
Verify the applicable terms before redistributing processed material.