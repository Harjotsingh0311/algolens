## Lecture 6: Randomized Algorithms

- Check matrix multiplication
- Quicksort

## Randomized or Probablistic Algorithms

What is a randomized algorithm?

- Algorithm that generates a random number r ∈ {1, ..., R} and makes decisions based on r's value.
- On the same input on different executions, a randomized algorithm may
- Run a different number of steps
- Produce a different output

Randomized algorithms can be broadly classified into two types- Monte Carlo and Las Vegas.

Monte Carlo

runs in polynomial time always output is correct with high probability Las Vegas runs in expected polynomial time output always correct

## Matrix Product

$$C = A \times B$$

Simple algorithm: O(n3 ) multiplications.

log2 7 ) = O(n2.81 ) Strassen: multiply two 2 × 2 matrices in 7 multiplications: O(n

Coppersmith-Winograd: O(n

2.376 )

## Matrix Product Checker

Given n ×n matrices A, B, C, the goal is to check if A ×B = C or not. Question. Can we do better than carrying out the full multiplication? We will see an O(n2 ) algorithm that:

- if A ×B = C, then Pr[output=YES] = 1.
- if A ×B . = C, then Pr[output=YES] ≤ 12

We will assume entries in matrices ∈ {0, 1} and also that the arithmetic is mod 2.

## Frievald's Algorithm

Choose a random binary vector r[1...n] such that Pr[ri = 1] = 1/2 independently for r = 1, ..., n. The algorithm will output 'YES' if A(Br) = Cr and 'NO' otherwise.

## Observation

The algorithm will take O(n2 ) time, since there are 3 matrix multiplications Br, A(Br) and Cr of a n ×n matrix by a n × 1 matrix.

## Analysis of Correctness if AB = C

Claim. If AB = C, then Pr[ABr = Cr] ≥ 1/2.

Let D = AB - C. Our hypothesis is thus that D = 0. Clearly, there exists r such that Dr 0. = Our goal is to show that there are many r such that Dr = 0. Specifically, Pr[Dr = 0] ≥ 1/2 for randomly chosen r.

D = AB-C = = 0 ⇒ ∃ i, j s.t. dij = 0. Fix vector v which is 0 in all coordinates except for vj = 1. (Dv)i = dij = 0 implying Dv = 0. Take any r that can be chosen by our algorithm. We are looking at the case where Dr = 0. Let

$$r ^ { \prime } = r + v$$

' ' Since v is 0 everywhere except vj , r is the same as r exept r = (rj + vj ) mod 2. j Thus, Dr' = D(r + v) = 0 + Dv 0. We see that there is a 1 to 1 correspondence = ' '' '' between r and r' , as if r = r + V = r + V then r = r . This implies that

' number of r for which Dr' = 0 ≥ number of r for which Dr = 0

From this we conclude that Pr[Dr = 0] ≥ 1/2

## Quicksort

Divide and conquer algorithm but work mostly in the divide step rather than combine. Sorts "in place" like insertion sort and unlike mergesort (which requires O(n) auxiliary space).

Different variants:

- Basic: good in average case
- Median-based pivoting: uses median finding
- Random: good for all inputs in expectation (Las Vegas algorithm)

Steps of quicksort:

- Divide: pick a pivot element x in A, partition the array into sub-arrays L, consisting of all elements &lt; x, G consisting of all elements &gt; x and E consisting of all elements = x.
- Conquer: recursively sort subarrays L and G
- Combine: trivial

## Basic Quicksort

Pivot around x = A[1] or A[n] (first or last element)

- Remove, in turn, each element y from A
- Insert y into L, E or G depending on the comparison with pivot x
- Each insertion and removal takes O(1) time
- Partition step takes O(n) time
- To do this in place: see CLRS p. 171

## Basic Quicksort Analysis

If input is sorted or reverse sorted, we are partitioning around the min or max element each time. This means one of L or G has n -1 elements, and the other 0. This gives:

$$T ( n ) & = T ( 0 ) + T ( n - 1 ) + \Theta ( n ) \\ & = \Theta ( 1 ) + T ( n - 1 ) + \Theta ( n ) \\ & = \Theta ( n ^ { 2 } )$$

However, this algorithm does well on random inputs in practice.

## Pivot Selection Using Median Finding

Can guarantee balanced L and G using rank/median selection algorithm that runs in Θ(n) time. The first Θ(n) below is for the pivot selection and the second for the partition step.

$$n$$

$$T ( n ) & = 2 T \left ( \frac { n } { 2 } \right ) + \Theta ( n ) + \Theta ( n ) \\ T ( n ) & = \Theta ( n \log n )$$

This algorithm is slow in practice and loses to mergesort.

## Randomized Quicksort

x is chosen at random from array A (at each recursion, a random choice is made). Expected time is O(n log n) for all input arrays A. See CLRS p.181-184 for the analysis of this algorithm; we will analyze a variant of this.

## "Paranoid" Quicksort

Repeat

choose pivot to be random element of A perform Partition

Until

resulting partition is such that

$$| L | \leq \frac { 3 } { 4 } | A | \text { and } | G | \leq \frac { 3 } { 4 } | A | \\$$

Recurse on L and G

## "Paranoid" Quicksort Analysis

Let's define a "good pivot" and a "bad pivot"­

Good pivot: sizes of L and G ≤ 34

Bad pivot: one of L and G is ≤ 34

n each

n each

bad pivots good pivots bad pivots

| n 4   | n 2   | n 4   |
|-------|-------|-------|

We see that a pivot is good with probability &gt; 1/2.

Let T (n) be an upper bound on the expected running time on any array of n size.

T(n) comprises:

- time needed to sort left subarray
- time needed to sort right subarray
- the number of iterations to get a good call. Denote as c · n the cost of the partition step

## Expectations

<!-- image -->

$$T ( n ) \leq m a x _ { n / 4 \leq i \leq 3 n / 4 } ( T ( i ) + T ( n - i ) ) + E ( \# \text {iterations} ) \cdot c n$$

Now, since probability of good pivot &gt; 21 ,

$$E ( \# i t e r a t i o n s ) \leq 2$$

$$T ( n ) \leq T \left ( \frac { n } { 4 } \right ) + T \left ( \frac { 3 n } { 4 \mathbb { I } } \right ) + 2 c n$$

We see in the figure that the height of the tree can be at most log 4 3 (2cn) no matter what branch we follow to the bottom. At each level, we do a total of 2cn work. Thus, expected runtime is T (n) = Θ(n log n)

## 6.046J / 18.410J Design and Analysis of Algorithms

Spring 2015

For information about citing these materials or our Terms of Use, visit: http://ocw.mit.e�u/terms.