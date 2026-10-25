# AlgoLens Gold Source Review Log - v0

**Status:** Partial review only. The gold set remains
`draft_needs_human_review`. No question has been fully verified.

## Review method

Compared the supplied extracted text with the original MIT OpenCourseWare
Lecture 6 typed-notes PDF, including visual inspection of printed pages 4-6.
The caption passages were read as extracted text but have not been checked
against the actual video.

Source: [MIT 6.046J Lecture 6 - Randomized Algorithms](https://ocw.mit.edu/courses/6-046j-design-and-analysis-of-algorithms-spring-2015/cb55cb123a557eed0738a1187a452c24_MIT6_046JS15_lec06.pdf)

## GQ023 - Median-pivot recurrence

- **Original typed notes:** printed page 4.
- **Caption interval:** 01:05:14.550-01:06:31.820, with follow-up at 01:06:31.820-01:07:31.390.
- **Source finding:** `T(n) = 2T(n/2) + Θ(n) + Θ(n)`, solving to `Θ(n log n)` worst-case time.
- **Interpretation:** the two linear terms represent median selection and partitioning.
- **Draft key-point change:** replaced the weaker `O(n log n)` statement with `Θ(n log n)`.
- **Passage-ID change:** none. Video spot-check and final evidence-label review remain outstanding.

## GQ025 - Paranoid Quicksort expected-time analysis

- **Original typed notes:** printed pages 5-6.
- **Caption intervals:** 01:18:07.280-01:19:14.620, 01:19:14.620-01:19:58.530, and 01:20:42.930-01:21:51.216.
- **Source finding:** good-pivot probability greater than `1/2`, expected attempts at most `2`, recurrence
  `T(n) ≤ T(n/4) + T(3n/4) + 2cn`, and expected runtime
  `Θ(n log n)`.
- **Extraction caveat:** the PDF formula in the extracted chunk is damaged. The original PDF is authoritative.
- **Draft key-point change:** added the expected-attempt bound and recurrence, and made the final asymptotic statement `Θ(n log n)`.
- **Passage-ID change:** none. Video spot-check and final evidence-label review remain outstanding.

## Review boundary

These checks support the corrected mathematical statements against the original
typed notes. They do not verify that the caption passages are faithful to the
recording or that every multi-hop gold passage is necessary. Both questions
remain in draft status.
