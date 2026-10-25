# Expectations — reviewed transcription (retrieval disabled)

**Status:** `reviewed_transcription_retrieval_disabled`

**Purpose:** A separately reviewed transcription prepared to correct the
damaged experimental extraction. It remains outside the answer-eligible
corpus until retrieval approval is granted separately.

## Provenance

- Source: MIT 6.046J, Lecture 6, *Randomized Algorithms*
- Original source: [Official MIT OpenCourseWare lecture notes](https://ocw.mit.edu/courses/6-046j-design-and-analysis-of-algorithms-spring-2015/cb55cb123a557eed0738a1187a452c24_MIT6_046JS15_lec06.pdf)
- Printed pages: 5–6
- Original PDF SHA-256: `fac37c9721e67c2f5723536ae412bd200ae7580675bd0f53b21f2878af39bc55`
- Review basis: visual inspection of the original PDF pages
- Project-owner approval: approved on 2026-10-25
- Retrieval eligibility: **false**

## Printed page 5 — Expected work and retry count

The notes define \(T(n)\) as an upper bound on expected running time for an
array of size \(n\). The work comprises sorting the left subarray, sorting the
right subarray, and the expected number of pivot attempts needed to obtain a
good call. A partition step costs \(cn\).

A good pivot occurs with probability greater than \(1/2\). Therefore, the
expected number of attempts is at most \(2\):

\[
E[\#\text{iterations}] \leq 2.
\]

The recurrence displayed on the page is:

\[
T(n) \leq
\max_{n/4 \leq i \leq 3n/4}
\left(T(i) + T(n-i)\right)
+ E[\#\text{iterations}] \cdot cn.
\]

## Printed page 6 — Recurrence and recursion tree

Substituting the expected-attempt bound gives:

\[
T(n) \leq T(n/4) + T(3n/4) + 2cn.
\]

The figure illustrates the work across the recursion tree. The notes state that
its height is at most \(\log_{4/3}(2cn)\), regardless of the branch followed to
the bottom. They state that the total work at each level is \(2cn\), and conclude:

\[
T(n) = \Theta(n \log n).
\]

## Transcription and review notes

1. The formulas above were prepared by visually reading the original PDF,
   rather than copying the damaged extracted equation text.
2. The height bound is transcribed as displayed: \(\log_{4/3}(2cn)\).
   The original expression is retained rather than silently normalized or
   rewritten.
3. This transcription was reviewed against the supplied original PDF and
   approved for integration on 2026-10-25. Retrieval remains disabled pending
   a separate retrieval-approval decision.
4. Do not replace `corpus/experiments/pdf_extraction/notes.md`, the existing
   chunk JSONL files, or any other original artifacts with this candidate.
