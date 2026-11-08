import random
from itertools import product

import pytest
from basic_search import FIXED_SEEDS, MAX_INT, MIN_INT, search


def test_common_seeds_are_fixed_and_cover_small_values_and_int_boundaries():
    assert FIXED_SEEDS == (0, 1, -1, 2, -2, MIN_INT, MIN_INT + 1, MAX_INT - 1, MAX_INT)
    assert len(set(FIXED_SEEDS)) == 9


@pytest.mark.parametrize("arity", [1, 2])
def test_exhaustion_tries_all_fixed_combinations_then_exact_random_budget(arity):
    seen = []

    def miss(arguments):
        seen.append(arguments)
        return False

    result = search(arity, miss, random.Random(0), random_trials=3)
    fixed = list(product(FIXED_SEEDS, repeat=arity))
    assert seen[:len(fixed)] == fixed
    assert len(seen) == len(fixed) + 3
    assert all(len(args) == arity and all(MIN_INT <= x <= MAX_INT for x in args) for args in seen)
    assert result.verdict == "unknown"
    assert result.witness is None
    assert result.fixed_trials == 9**arity
    assert result.random_trials == 3


@pytest.mark.parametrize("witness", [(0,), (MIN_INT,), (MAX_INT,), (0, 0), (0, 1), (MIN_INT, MAX_INT)])
def test_first_fixed_hit_returns_witness_without_random_sampling(witness, monkeypatch):
    rng = random.Random(0)

    def unexpected_random(*args):
        pytest.fail("Random generation must not run after a fixed hit")

    monkeypatch.setattr(rng, "randint", unexpected_random)
    seen = []

    def hit(arguments):
        seen.append(arguments)
        return arguments == witness

    result = search(len(witness), hit, rng)
    assert result.verdict == "reachable"
    assert result.witness == witness
    assert seen[-1] == witness
    assert result.fixed_trials == len(seen)
    assert result.random_trials == 0


def test_random_phase_draws_independent_full_range_arguments_and_stops(monkeypatch):
    rng = random.Random(0)
    draws = iter([17, 23])
    calls = []

    def draw(low, high):
        calls.append((low, high))
        return next(draws)

    monkeypatch.setattr(rng, "randint", draw)
    result = search(2, lambda arguments: arguments == (17, 23), rng, random_trials=1000)
    assert result.verdict == "reachable"
    assert result.witness == (17, 23)
    assert result.fixed_trials == 81
    assert result.random_trials == 1
    assert calls == [(MIN_INT, MAX_INT), (MIN_INT, MAX_INT)]


def test_zero_random_budget_is_seed_only_not_unreachable():
    result = search(1, lambda arguments: arguments == (100003,), random.Random(0), random_trials=0)
    assert result.verdict == "unknown"
    assert result.witness is None
    assert result.fixed_trials == 9
    assert result.random_trials == 0


def test_replaying_seed_reproduces_candidate_sequence():
    def candidates():
        seen = []

        def miss(arguments):
            seen.append(arguments)
            return False

        search(2, miss, random.Random(42), random_trials=10)
        return seen

    assert candidates() == candidates()


@pytest.mark.parametrize("arity", [0, 3, True, "1"])
def test_invalid_arity_is_an_error(arity):
    with pytest.raises(ValueError, match="one or two"):
        search(arity, lambda arguments: True, random.Random(0))


@pytest.mark.parametrize("budget", [-1, True, "1000", 1.5])
def test_invalid_budget_is_an_error(budget):
    with pytest.raises(ValueError, match="nonnegative integer"):
        search(1, lambda arguments: True, random.Random(0), random_trials=budget)


def test_interpreter_failures_are_not_unknown_verdicts():
    def broken(arguments):
        raise ValueError("Unsupported instruction")

    with pytest.raises(ValueError, match="Unsupported instruction"):
        search(1, broken, random.Random(0))
