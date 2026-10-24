<!-- source_page: 1 -->

Randomized Algorithms 6.046J Spring 2015 

Lecture 6 

# **Lecture 6: Randomized Algorithms** 

- Check matrix multiplication 

- Quicksort 

## **Randomized or Probablistic Algorithms** 

What is a randomized algorithm? 

- Algorithm that generates a random number _r ∈{_ 1 _, ..., R}_ and makes decisions based on _r_ ’s value. 

- On the same input on different executions, a randomized algorithm may 

   - Run a different number of steps 

   - Produce a different output 

Randomized algorithms can be broadly classified into two types- Monte Carlo and Las Vegas. 

<u>Monte Carlo</u> Las Vegas runs in polynomial time always runs in expected polynomial time output is correct with high probability output always correct 

## **Matrix Product** 



<!-- Start of picture text -->
C = A × B<br><!-- End of picture text -->

Simple algorithm: _O_ ( _n_<sup>3</sup> ) multiplications. 

Strassen: multiply two 2 _×_ 2 matrices in 7 multiplications: _O_ ( _n_ log2 7) = _O_ ( _n_ 2 _._ 81) Coppersmith-Winograd: _O_ ( _n_ 2 _._ 376) 

1

<!-- source_page: 2 -->

Randomized Algorithms 6.046J Spring 2015 

Lecture 6 

## **Matrix Product Checker** 

Given _n × n_ matrices _A, B, C_ , the goal is to check if _A × B_ = _C_ or not. **Question.** Can we do better than carrying out the full multiplication? We will see an _O_ ( _n_<sup>2</sup> ) algorithm that: 

- if _A × B_ = _C_ , then _Pr_ [output=YES] = 1. 



<!-- Start of picture text -->
• if A × B = C , then Pr [output=YES] ≤ 1 2.<br><!-- End of picture text -->

We will assume entries in matrices _∈{_ 0 _,_ 1 _}_ and also that the arithmetic is mod 2. 

## **Frievald’s Algorithm** 

Choose a random binary vector _r_ [1 _...n_ ] such that _Pr_ [ _ri_ = 1] = 1 _/_ 2 independently for _r_ = 1 _, ..., n_ . The algorithm will output ’YES’ if _A_ ( _Br_ ) = _Cr_ and ’NO’ otherwise. 

### **Observation** 

The algorithm will take _O_ ( _n_<sup>2</sup> ) time, since there are 3 matrix multiplications _Br_ , _A_ ( _Br_ ) and _Cr_ of a _n × n_ matrix by a _n ×_ 1 matrix. 

### **Analysis of Correctness if** _AB_ = _C_ 

**Claim.** If _AB_ = _C_ , then _Pr_ [ _ABr_ = _Cr_ ] _≥_ 1 _/_ 2. 

Let _D_ = _AB − C_ . Our hypothesis is thus that _D_ = 0. Clearly, there exists _r_ such that _Dr_ = 0. Our goal is to show that there are many _r_ such that _Dr_ = 0. Specifically, _Pr_ [ _Dr_ = 0] _≥_ 1 _/_ 2 for randomly chosen _r_ . 

_D_ = _AB −C_ = 0 = _⇒∃ i, j_ s.t. _dij_ = 0. Fix vector _v_ which is 0 in all coordinates except for _vj_ = 1. ( _Dv_ ) _i_ = _dij_ = 0 implying _Dv_ = 0. Take any _r_ that can be chosen by our algorithm. We are looking at the case where _Dr_ = 0. Let 



<!-- Start of picture text -->
r' = r + v<br><!-- End of picture text -->

Since _v_ is 0 everywhere except _vj_ , _r'_ is the same as _r_ exept _rj'_ = ( _rj_ + _vj_ ) mod 2. = Thus, _Dr_<sup>_'_</sup> = _D_ ( _r_ + _v_ ) = 0 + _Dv_ 0. We see that there is a 1 to 1 correspondence between _r_ and _r_<sup>_'_</sup> , as if _r'_ = _r_ + _V_ = _r''_ + _V_ then _r_ = _r''_ . This implies that 

number of _r'_ for which _Dr_<sup>_'_</sup> = 0 _≥_ number of _r_ for which _Dr_ = 0 

From this we conclude that _Pr_ [ _Dr_ = 0] _≥_ 1 _/_ 2 

2

<!-- source_page: 3 -->

Randomized Algorithms 6.046J Spring 2015 

Lecture 6 

## **Quicksort** 

Divide and conquer algorithm but work mostly in the divide step rather than combine. Sorts “in place” like insertion sort and unlike mergesort (which requires _O_ ( _n_ ) auxiliary space). 

Different variants: 

- Basic: good in average case 

- Median-based pivoting: uses median finding 

- Random: good for all inputs in expectation (Las Vegas algorithm) 

Steps of quicksort: 

- Divide: pick a pivot element _x_ in _A_ , partition the array into sub-arrays _L_ , consisting of all elements _< x_ , _G_ consisting of all elements _> x_ and _E_ consisting of all elements = _x_ . 

- Conquer: recursively sort subarrays _L_ and _G_ 

- Combine: trivial 

### **Basic Quicksort** 

Pivot around _x_ = _A_ [1] or _A_ [ _n_ ] (first or last element) 

- Remove, in turn, each element _y_ from _A_ 

- Insert _y_ into _L_ , _E_ or _G_ depending on the comparison with pivot _x_ 

- Each insertion and removal takes _O_ (1) time 

- Partition step takes _O_ ( _n_ ) time 

- To do this in place: see CLRS p. 171 

3

<!-- source_page: 4 -->

Randomized Algorithms 6.046J Spring 2015 

Lecture 6 

#### **Basic Quicksort Analysis** 

If input is sorted or reverse sorted, we are partitioning around the min or max element each time. This means one of _L_ or _G_ has _n −_ 1 elements, and the other 0. This gives: 



<!-- Start of picture text -->
T ( n ) = T (0) + T ( n − 1) + Θ( n )<br>= Θ(1) + T ( n − 1) + Θ( n )<br>= Θ( n 2 )<br><!-- End of picture text -->

However, this algorithm does well on random inputs in practice. 

### **Pivot Selection Using Median Finding** 

Can guarantee balanced _L_ and _G_ using rank/median selection algorithm that runs in Θ( _n_ ) time. The first Θ( _n_ ) below is for the pivot selection and the second for the partition step. 



<!-- Start of picture text -->
n<br>T ( n ) = 2 T + Θ( n ) + Θ( n )<br>( 2 )<br>T ( n ) = Θ( n log n )<br><!-- End of picture text -->

This algorithm is slow in practice and loses to mergesort. 

### **Randomized Quicksort** 

_x_ is chosen at random from array _A_ (at each recursion, a random choice is made). Expected time is _O_ ( _n_ log _n_ ) for all input arrays _A_ . See CLRS p.181-184 for the analysis of this algorithm; we will analyze a variant of this. 

### **“Paranoid” Quicksort** 

Repeat 

choose pivot to be random element of _A_ perform Partition Until resulting partition is such that _|L| ≤_<sup><u>3</u></sup> 4 _|A|_ and _|G| ≤_<sup><u>3</u></sup> 4 _|A|_ Recurse on _L_ and _G_ 

4

<!-- source_page: 5 -->

Randomized Algorithms 

6.046J Spring 2015 

Lecture 6 

#### **“Paranoid” Quicksort Analysis** 

Let’s define a ”good pivot” and a ”bad pivot”­ 

Good pivot: sizes of _L_ and _G ≤_<sup><u>3</u></sup> 4<sup>_n_each</sup> Bad pivot: one of _L_ and _G_ is _≤_<sup><u>3</u></sup> 4<sup>_n_each</sup> 

#### bad pivots good pivots bad pivots 



<!-- Start of picture text -->
n n n<br>4 2 4<br><!-- End of picture text -->

We see that a pivot is good with probability _>_ 1 _/_ 2. 

Let _T_ ( _n_ ) be an upper bound on the expected running time on any array of _n_ size. T(n) comprises: 

- time needed to sort left subarray 

- time needed to sort right subarray 

- the number of iterations to get a g ~~o~~ od call. Denote as _c · n_ the cost of the partition step 

#### **Expectations** 



<!-- Start of picture text -->
2cn<br>(2cn)/4 3(2cn)/4<br>(2cn)/16 3(2cn)/16 9(2cn)/16<br>O(1) O(1)<br><!-- End of picture text -->

_T_ ( _n_ ) _≤ maxn/_ 4 _≤i≤_ 3 _n/_ 4( _T_ ( _i_ ) + _T_ ( _n − i_ )) + _E_ (#iterations) _· cn_ Now, since probability of good pivot _>_ <u>12</u> , 

_E_ (# _iterations_ ) _≤_ 2 

5

<!-- source_page: 6 -->

Randomized Algorithms 6.046J Spring 2015 

Lecture 6 



<!-- Start of picture text -->
n 3 n<br>T ( n ) ≤ T + T + 2 cn<br>( 4 ) 4<br><!-- End of picture text -->

We see in the figure that the height of the tree can be at most log <u>43</u><sup>(2</sup><sup>_cn_)nomatter</sup> what branch we follow to the bottom. At each level, we do a total of 2 _cn_ work. Thus, expected runtime is _T_ ( _n_ ) = Θ( _n_ log _n_ ) 

6

<!-- source_page: 7 -->

MIT OpenCourseWare http://ocw.mit.edu 

6.046J / 18.410J Design and Analysis of Algorithms Spring 2015 

For information about citing these materials or our Terms of Use, visit: http://ocw.mit.edu/terms.
