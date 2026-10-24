# Lecture 6 PDF Extraction Evaluation

**Date:** 2026-10-25
**Status:** Initial comparison complete; canonical extraction not yet selected.

## Source and integrity

- Course: MIT 6.046J, Design and Analysis of Algorithms, Spring 2015.
- Lecture: Lecture 6, Randomized Algorithms.
- Source: [Official MIT OpenCourseWare lecture PDF](https://ocw.mit.edu/courses/6-046j-design-and-analysis-of-algorithms-spring-2015/cb55cb123a557eed0738a1187a452c24_MIT6_046JS15_lec06.pdf).
- Source SHA-256: `fac37c9721e67c2f5723536ae412bd200ae7580675bd0f53b21f2878af39bc55`.
- The file has seven PDF pages.

## Extraction experiments

The measurements below were printed by the local extraction/comparison runs.
Candidate formula/topic counts are pattern-match counts, not accuracy scores.

| Output file | Method | Observed result |
|---|---|---|
| `notes.md` | PyMuPDF4LLM, page-aware Markdown | 7,613 extracted characters, 237 lines, 29 candidate formula/topic lines |
| `notes_docling_cuda.md` | Docling, formula enrichment, CUDA accelerator configured | 6,011 characters, 173 lines, 33 candidate lines; conversion about 62.18 seconds |
| `notes_docling_cuda_torch_ocr.md` | Docling, formula enrichment, CUDA accelerator configured, Torch OCR backend | 6,011 characters, 173 lines, 33 candidate lines; conversion about 51.32 seconds |

The first Docling run warned that the CUDA execution provider was unavailable to its ONNX Runtime OCR backend. The Torch OCR run removed those provider warnings. PyTorch reported 2.26 GiB and 2.30 GiB of peak allocated GPU memory in the two runs respectively. These memory readings do not establish that every stage of the pipeline ran on the GPU.

The two Docling runs returned the same character count, line count, and candidate count. The listed formula examples remained malformed. The outputs have not been proven byte-identical.

## Known extraction defects

The Docling output contains examples such as:

- `Pr[output=YES] ≤ 12`, where the source shows an upper bound of `1/2`.
- `Good pivot: sizes of L and G ≤ 34`, where the source shows a bound involving `3n/4`.
- A malformed recurrence around the term `T(3n/4)`.

These defects can change mathematical meaning. More formula matches do not imply higher extraction accuracy.

## Selected source checks

The separately stored `corpus/processed/notes_formula_review.md` contains selected formulas checked directly against the source PDF:

- Printed page 2: Matrix Product Checker and Freivalds' Algorithm probability bounds.
- Printed page 4: Basic Quicksort worst-case recurrence, median-based pivot selection, and randomized Quicksort statement.
- Printed pages 5–6: Paranoid Quicksort pivot bounds and expected-time recurrences.

This is a review of selected formula-bearing passages, not a complete validation of every sentence, diagram, or equation in the lecture.

## Current decision

- Preserve the extraction experiments as separate artifacts.
- Do not designate any automatic output as the trusted canonical notes yet.
- Keep manually checked formula excerpts separate from automatically extracted passages.
- Before final chunking, preserve document/page provenance and a review-status field.
- The project is primarily focused on randomized Quicksort. Whether Matrix Product Checker and Freivalds' Algorithm should be included as secondary answer topics remains an explicit scope decision.

## Attribution and reuse

The lecture PDF is MIT OpenCourseWare course material. Review the applicable source notices before redistributing derived content. MIT OpenCourseWare's general license is [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/), subject to source-specific notices and exceptions.

Derived source content must retain appropriate attribution, indicate changes, remain noncommercial, and follow the applicable share-alike terms. This source-content requirement is distinct from the license chosen for independently written application code.
