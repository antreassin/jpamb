import random
from collections.abc import Callable, Hashable, Iterable
from dataclasses import dataclass
from typing import Literal

Arguments = tuple[int, ...]


@dataclass(frozen=True)
class FuzzResult:
    verdict: Literal["reachable", "unknown"]
    witness: Arguments | None
    fixed_executions: int
    mutation_executions: int
    corpus_size: int
    covered_instructions: int

    @property
    def executions(self) -> int:
        return self.fixed_executions + self.mutation_executions


def mutate_one(parent: Arguments, rng: random.Random) -> Arguments:
    index = rng.randrange(len(parent))
    value = parent[index]
    if rng.randrange(2) == 0:
        value += rng.choice((-1, 1))
    else:
        value ^= 1 << rng.randrange(32)
    value = (value + 2**31) % 2**32 - 2**31
    return parent[:index] + (value,) + parent[index + 1 :]


def fuzz(
    seeds: Iterable[Arguments],
    observe: Callable[[Arguments], tuple[frozenset[Hashable], bool]],
    *,
    rng: random.Random,
    total_executions: int,
    mutate: Callable[[Arguments, random.Random], Arguments] = mutate_one,
) -> FuzzResult:
    if type(total_executions) is not int or total_executions < 0:
        raise ValueError("total_executions must be a nonnegative integer")

    corpus: list[Arguments] = []
    seen: set[Hashable] = set()
    fixed_executions = mutation_executions = 0
    witness = None
    seed_inputs = iter(seeds)
    for _ in range(total_executions):
        candidate = next(seed_inputs, None)
        if candidate is not None:
            fixed_executions += 1
        elif corpus:
            candidate = mutate(rng.choice(corpus), rng)
            mutation_executions += 1
        else:
            break

        coverage, pair_hit = observe(candidate)
        if not coverage.issubset(seen):
            corpus.append(candidate)
            seen.update(coverage)
        if pair_hit:
            witness = candidate
            break

    return FuzzResult(
        "reachable" if witness is not None else "unknown",
        witness,
        fixed_executions,
        mutation_executions,
        len(corpus),
        len(seen),
    )
