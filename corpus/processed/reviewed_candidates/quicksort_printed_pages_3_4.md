# Quicksort - candidate transcription summary (owner review pending)

**Status:** `candidate_transcription_pending_owner_review`

**Retrieval eligibility:** **false**

## Provenance

- Source: MIT 6.046J, Lecture 6, *Randomized Algorithms*
- Original source: [Official MIT OpenCourseWare lecture notes](https://ocw.mit.edu/courses/6-046j-design-and-analysis-of-algorithms-spring-2015/cb55cb123a557eed0738a1187a452c24_MIT6_046JS15_lec06.pdf)
- Printed pages: 3-4
- Original PDF SHA-256: `fac37c9721e67c2f5723536ae412bd200ae7580675bd0f53b21f2878af39bc55`
- Preparation basis: visual inspection of the original PDF pages
- Project-owner approval: pending
- Retrieval eligibility: **false**
- This is a concise, page-specific transcription summary, not a replacement for the original notes.

## Printed page 3 - Quicksort overview

Quicksort is presented as a divide-and-conquer algorithm that does most of its work during partitioning; combining is trivial. The notes describe it as in-place, contrasting it with mergesort's \(O(n)\) auxiliary space.

The listed variants are basic Quicksort (good in the average case), median-based pivoting, and randomized Quicksort (good for all inputs in expectation, as a Las Vegas algorithm).

For pivot \(x\), partition the array into \(L\) (elements \(<x\)), \(E\) (elements \(=x\)), and \(G\) (elements \(>x\)). Recursively sort \(L\) and \(G\). The basic version chooses the first or last array element as its pivot. The notes describe removing elements one by one and inserting them into \(L\), \(E\), or \(G\) according to comparison with the pivot. Each insertion and removal costs \(O(1)\), and partitioning costs \(O(n)\). The in-place implementation is referenced to CLRS, p. 171.

## Printed page 4 - Analysis and variants

For sorted or reverse-sorted input, first/last pivoting selects an extreme element, leaving subarrays of sizes \(0\) and \(n-1\). The notes give the recurrence:

\[
T(n)=T(0)+T(n-1)+\Theta(n)
\]

\[
=\Theta(1)+T(n-1)+\Theta(n)
\]

\[
=\Theta(n^2).
\]

For median-based pivot selection, the notes state that balanced subarrays can be guaranteed using a rank/median selection algorithm taking \(\Theta(n)\) time. They give:

\[
T(n)=2T(n/2)+\Theta(n)+\Theta(n)
\]

\[
T(n)=\Theta(n\log n).
\]

The notes remark that this algorithm is slow in practice and loses to mergesort.

For randomized Quicksort, a random array element is chosen as pivot at each recursive call. The notes state expected \(O(n\log n)\) time for all input arrays.

The page also describes "Paranoid" Quicksort: repeatedly choose a random pivot and partition until both sides satisfy

\[
|L|\leq \frac{3}{4}|A|
\quad\text{and}\quad
|G|\leq \frac{3}{4}|A|.
\]

Then recurse on \(L\) and \(G\).

## Review notes

1. The content is summarized from printed pages 3 and 4; citations must stay page-specific.
2. Mathematical expressions have been manually transcribed from the rendered PDF rather than copied from the damaged extraction.
3. The candidate has not yet received project-owner approval and must remain retrieval-disabled.
4. Do not replace the experimental extraction, existing chunk JSONL files, or the approved pages 5-6 transcription.
