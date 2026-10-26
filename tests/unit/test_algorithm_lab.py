from __future__ import annotations

import pytest

from algolens.algorithm_lab import randomized_quicksort, run_experiment


def test_randomized_quicksort_sorts_without_mutating_input() -> None:
    values = [7, 2, 5, 2, -1, 9, 0]
    original = values.copy()

    run = randomized_quicksort(values, seed=17)

    assert run.sorted_values == sorted(values)
    assert run.input_values == original
    assert values == original
    assert run.comparisons == sum(step.comparisons for step in run.trace)


def test_randomized_quicksort_is_reproducible_for_a_seed() -> None:
    values = [8, 1, 4, 7, 3, 2, 6, 5]

    first = randomized_quicksort(values, seed=123)
    second = randomized_quicksort(values, seed=123)

    assert first == second


def test_randomized_quicksort_handles_empty_and_singleton_inputs() -> None:
    assert randomized_quicksort([], seed=1).sorted_values == []
    singleton = randomized_quicksort([42], seed=1)
    assert singleton.sorted_values == [42]
    assert singleton.comparisons == 0
    assert singleton.trace == []


def test_experiment_is_reproducible_and_reports_empirical_metrics() -> None:
    first = run_experiment(n=30, trials=8, seed=5)
    second = run_experiment(n=30, trials=8, seed=5)

    assert first == second
    assert first["n"] == 30
    assert first["trials"] == 8
    assert first["min_comparisons"] <= first["mean_comparisons"]
    assert first["mean_comparisons"] <= first["max_comparisons"]
    assert first["comparisons_per_n_log2_n"] > 0
    assert first["theoretical_asymptotic_constant"] == pytest.approx(1.38629436)


def test_experiment_accepts_zero_items() -> None:
    report = run_experiment(n=0, trials=2, seed=0)

    assert report["mean_comparisons"] == 0
    assert report["comparisons_per_n_log2_n"] == 0


@pytest.mark.parametrize("n,trials", [(-1, 1), (5, 0)])
def test_experiment_rejects_invalid_arguments(n: int, trials: int) -> None:
    with pytest.raises(ValueError):
        run_experiment(n=n, trials=trials)
