from __future__ import annotations

import argparse
import json
import math
import random
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class PartitionStep:
    """One partition operation recorded for the teaching trace."""

    low: int
    high: int
    pivot: int
    comparisons: int
    left_size: int
    right_size: int


@dataclass(frozen=True)
class QuicksortRun:
    """Result of one reproducible randomized Quicksort execution."""

    input_values: list[int]
    sorted_values: list[int]
    seed: int
    comparisons: int
    trace: list[PartitionStep]


def randomized_quicksort(values: list[int], *, seed: int = 0) -> QuicksortRun:
    """Sort a copy using randomized Lomuto partitioning and record comparisons.

    Each non-pivot element is compared with the selected pivot exactly once.
    The input list is not mutated. Equal values are supported.
    """
    original = list(values)
    result = list(values)
    rng = random.Random(seed)
    trace: list[PartitionStep] = []
    comparison_count = 0

    def sort(low: int, high: int) -> None:
        nonlocal comparison_count
        if low >= high:
            return

        pivot_index = rng.randint(low, high)
        result[pivot_index], result[high] = result[high], result[pivot_index]
        pivot = result[high]
        boundary = low
        comparisons_before = comparison_count

        for current in range(low, high):
            comparison_count += 1
            if result[current] <= pivot:
                result[boundary], result[current] = result[current], result[boundary]
                boundary += 1

        result[boundary], result[high] = result[high], result[boundary]
        trace.append(
            PartitionStep(
                low=low,
                high=high,
                pivot=pivot,
                comparisons=comparison_count - comparisons_before,
                left_size=boundary - low,
                right_size=high - boundary,
            )
        )
        sort(low, boundary - 1)
        sort(boundary + 1, high)

    sort(0, len(result) - 1)
    return QuicksortRun(
        input_values=original,
        sorted_values=result,
        seed=seed,
        comparisons=comparison_count,
        trace=trace,
    )


def run_experiment(*, n: int = 100, trials: int = 100, seed: int = 0) -> dict[str, Any]:
    """Estimate randomized Quicksort comparisons on shuffled permutations."""
    if n < 0:
        raise ValueError("n must be non-negative.")
    if trials < 1:
        raise ValueError("trials must be at least 1.")

    master_rng = random.Random(seed)
    comparison_counts: list[int] = []
    for _ in range(trials):
        values = list(range(n))
        master_rng.shuffle(values)
        trial_seed = master_rng.randrange(0, 2**63)
        comparison_counts.append(randomized_quicksort(values, seed=trial_seed).comparisons)

    mean_comparisons = sum(comparison_counts) / trials
    denominator = n * math.log2(n) if n > 1 else 0.0
    normalized = mean_comparisons / denominator if denominator else 0.0
    return {
        "n": n,
        "trials": trials,
        "seed": seed,
        "mean_comparisons": mean_comparisons,
        "min_comparisons": min(comparison_counts),
        "max_comparisons": max(comparison_counts),
        "comparisons_per_n_log2_n": normalized,
        "theoretical_asymptotic_constant": 1.3862943611198906,
        "interpretation": (
            "Finite-trial empirical estimate, not a guarantee. The asymptotic expected "
            "comparison count for randomized Quicksort is approximately "
            "1.386 * n * log2(n); results vary with n and trial count."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the AlgoLens randomized Quicksort lab.")
    parser.add_argument("--n", type=int, default=100, help="Number of distinct values.")
    parser.add_argument("--trials", type=int, default=100, help="Number of shuffled trials.")
    parser.add_argument("--seed", type=int, default=0, help="Master random seed.")
    parser.add_argument(
        "--trace",
        action="store_true",
        help="Include a single example trace in the JSON output.",
    )
    args = parser.parse_args()
    report = run_experiment(n=args.n, trials=args.trials, seed=args.seed)
    if args.trace:
        example = randomized_quicksort(list(range(args.n)), seed=args.seed)
        report["example_run"] = asdict(example)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
