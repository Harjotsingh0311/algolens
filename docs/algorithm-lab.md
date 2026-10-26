# Randomized Quicksort lab

The proposal calls for an executable lecture lab that makes randomized Quicksort's comparison
count observable. This module implements randomized Lomuto partitioning with a fixed seed,
counts element-to-pivot comparisons, and records a partition trace.

## Run an experiment

From the repository root:

```powershell
uv run python -m algolens.algorithm_lab --n 100 --trials 100 --seed 42
```

The JSON output reports the mean, minimum, and maximum comparison counts across shuffled
permutations, plus the empirical ratio (C/(n\log_2 n)). To include one example execution's
partition trace:

```powershell
uv run python -m algolens.algorithm_lab --n 20 --trials 10 --seed 42 --trace
```

## Interpretation

For randomized Quicksort on distinct keys, the expected comparison count grows asymptotically
as approximately (2n\ln n \approx 1.386 n\log_2 n). The lab reports an empirical finite-trial
estimate; it is not a guarantee, and small inputs/trial counts can vary. The random seed makes
the experiment reproducible.

This is a teaching/measurement utility, not a replacement for the RAG evidence gate. Its
algorithmic claims should be connected to reviewed lecture passages before being used as
answer evidence. The input list is copied, duplicates are supported, and tests check ordering,
seed reproducibility, comparison accounting, and invalid arguments.
