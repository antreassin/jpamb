"""A: fixed small/boundary inputs, followed by bounded random testing."""

import random
from collections.abc import Callable
from dataclasses import dataclass
from itertools import product
from typing import Literal

MIN_INT, MAX_INT = -(2**31), 2**31 - 1
FIXED_SEEDS = (0, 1, -1, 2, -2, MIN_INT, MIN_INT + 1, MAX_INT - 1, MAX_INT)
DEFAULT_RANDOM_TRIALS = 1000


@dataclass(frozen=True)
class SearchResult:
    verdict: Literal["reachable", "unknown"]
    witness: tuple[int, ...] | None
    fixed_trials: int
    random_trials: int


def search(
    arity: int,
    hits_target: Callable[[tuple[int, ...]], bool],
    rng: random.Random,
    random_trials: int = DEFAULT_RANDOM_TRIALS,
) -> SearchResult:
    """A hit is a concrete witness; exhausting the budget proves nothing."""
    if type(arity) is not int or arity not in (1, 2):
        raise ValueError("A supports one or two int arguments")
    if type(random_trials) is not int or random_trials < 0:
        raise ValueError("random_trials must be a nonnegative integer")

    # Cartesian products include equal pairs, ordered pairs and int boundaries.
    for fixed_count, arguments in enumerate(product(FIXED_SEEDS, repeat=arity), start=1):
        if hits_target(arguments):
            return SearchResult("reachable", arguments, fixed_count, 0)

    fixed_count = len(FIXED_SEEDS) ** arity
    for random_count in range(1, random_trials + 1):
        arguments = tuple(rng.randint(MIN_INT, MAX_INT) for _ in range(arity))
        if hits_target(arguments):
            return SearchResult("reachable", arguments, fixed_count, random_count)

    return SearchResult("unknown", None, fixed_count, random_trials)
