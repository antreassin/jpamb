"""A: try fixed inputs, then random inputs; report a witness hitting both targets.

A missed search is unknown, never an unreachability proof.
"""

import random
from collections.abc import Callable
from dataclasses import dataclass
from itertools import product
from typing import Literal

MIN_INT, MAX_INT = -(2**31), 2**31 - 1
FIXED_SEEDS = (0, 1, -1, 2, -2, MIN_INT, MIN_INT + 1, MAX_INT - 1, MAX_INT)
DEFAULT_RANDOM_TRIALS = 1000
MAX_STEPS = 10_000


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


def analyse(inputs: dict, disassembly: str, seed: int,
            random_trials: int = DEFAULT_RANDOM_TRIALS) -> list[dict]:
    """Run the same bounded input search independently for each query."""
    from analysis_common import prepare_queries, query_metadata
    from pair_dataset import Unsupported, prepared_queries, supported_method
    from validate import execute_bytecode

    if type(seed) is not int:
        raise ValueError("seed must be an integer")
    if type(random_trials) is not int or random_trials < 0:
        raise ValueError("random_trials must be a nonnegative integer")
    paired = inputs["schema_version"] == 2
    queries = prepared_queries(inputs, disassembly) if paired else [
        (query_metadata(query, method), method)
        for query, method, _ in prepare_queries(inputs, disassembly)
    ]
    rng = random.Random(seed)
    results = []
    for query, method in queries:
        result = dict(query)
        if paired:
            try:
                supported_method(query, method)
                if method["descriptor"] not in ("(I)I", "(II)I"):
                    raise Unsupported("A supports only one or two int arguments")
            except Unsupported as exc:
                result.update(verdict="unsupported", reason=str(exc), witness=None)
                results.append(result)
                continue
            method = {**method, "target_indices": [
                target["instruction_indices"] for target in query["targets"]]}

        cutoffs = 0

        def hits(arguments):
            nonlocal cutoffs
            _, reached = execute_bytecode(method, arguments, max_steps=MAX_STEPS) if paired else (
                execute_bytecode(method, arguments))
            if reached is None:
                cutoffs += 1
            return reached is True

        found = search(len(method["descriptor"]) - 3, hits, rng, random_trials)
        result.update(
            verdict=found.verdict,
            witness=list(found.witness) if found.witness is not None else None,
            fixed_trials=found.fixed_trials, random_trials=found.random_trials,
            witness_phase=None if found.witness is None else (
                "random" if found.random_trials else "fixed"),
        )
        if paired:
            result.update(step_limit=MAX_STEPS, cutoff_trials=cutoffs)
            if cutoffs:
                result["reason"] = f"{cutoffs} executions hit the {MAX_STEPS}-instruction bound"
        results.append(result)
    return results
