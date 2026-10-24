# AlgoLens Formula Review — MIT 6.046J Lecture 6

**Review status:** Selected equations checked against the official source PDF on 2026-10-25. This is a partial review, not a complete audit of every formula or paragraph in the lecture.

This file is a separate reviewed formula reference. It does not replace `notes.md` or either Docling experiment. Where automatic extraction conflicts with this reference, inspect the cited page of the original PDF.

Source: MIT 6.046J, Design and Analysis of Algorithms, Lecture 6.
Source file: L06_TYPED_NOTES.pdf
Expected SHA-256:
fac37c9721e67c2f5723536ae412bd200ae7580675bd0f53b21f2878af39bc55

## Matrix Product Checker — secondary topic; confirm project scope
Source PDF printed page 2.

If AB = C:
Pr[output = YES] = 1

If AB != C:
Pr[output = YES] <= 1/2

## Freivalds' Algorithm
Source PDF printed page 2.

If AB != C:
Pr[ABr != Cr] >= 1/2

Let D = AB - C. For the incorrect-product case, D != 0, and the notes
establish Pr[Dr != 0] >= 1/2 for a randomly chosen binary vector r.

## Basic Quicksort Worst-Case Analysis
Source PDF printed page 4.

T(n) = T(0) + T(n - 1) + Theta(n)
     = Theta(1) + T(n - 1) + Theta(n)
     = Theta(n^2)

## Median-Based Pivot Selection
Source PDF printed page 4.

T(n) = 2T(n/2) + Theta(n) + Theta(n)
T(n) = Theta(n log n)

## Randomized Quicksort
Source PDF printed page 4.

The notes state that expected running time is O(n log n) for all input arrays.

## Paranoid Quicksort: Good Pivot
Source PDF printed page 5.

For a good pivot, both resulting subarrays L and G have size at most
3n/4 each.

The notes state that a pivot is good with probability greater than 1/2
and that the expected number of iterations until a good pivot is at most 2.

## Paranoid Quicksort: Expected-Time Analysis
Source PDF printed pages 5-6.

T(n) <= max over n/4 <= i <= 3n/4 of
       (T(i) + T(n - i)) + E[iterations] * c*n

E[iterations] <= 2

T(n) <= T(n/4) + T(3n/4) + 2*c*n

The notes conclude that expected runtime is Theta(n log n).

## Review policy

This file covers selected formula-bearing passages, not the whole lecture.
It must not be treated as a complete replacement for the lecture notes.
The matrix-product material is marked secondary because the tutor's primary
focus is Quicksort; confirm whether it belongs in the approved answer scope.
