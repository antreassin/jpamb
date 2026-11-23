
"""Comparing A and B using the same execution budget"""

from __future__ import annotations

import argparse
import json
import random
import sys
import tempfile
import time
from collections.abc import Callable
from dataclasses import asdict
from itertools import islice, product
from pathlib import Path

from group15 import run_pairs
from group15.dictionary import FIXED_SEEDS, SearchResult, dictionary_values, search


POLICIES = ("A", "B")


def _budgeted_search(
    arity: int,
    constants: tuple[int, ...],
    observe: Callable[[tuple[int, ...]], bool],
    rng: random.Random,
    cap: int,
) -> SearchResult:
    fixed_size = len(FIXED_SEEDS) ** arity

    # Handle budgets smaller than the fixed input set
    if cap < fixed_size:
        prefix = islice(product(FIXED_SEEDS, repeat=arity), cap)
        for attempt, arguments in enumerate(prefix, 1):
            if observe(arguments):
                return SearchResult("reachable", arguments, attempt, 0, 0)
        return SearchResult("unknown", None, cap, 0, 0)

    extra_tuples = len(dictionary_values(constants)) ** arity - fixed_size
    remaining = cap - fixed_size
    dictionary_trials = min(remaining, extra_tuples)

    return search(
        arity,
        constants,
        observe,
        rng,
        dictionary_trials=dictionary_trials,
        random_trials=remaining - dictionary_trials,
    )


def run_arm(
    prepared: run_pairs.PreparedBenchmark,
    method: str,
    strategy: str,
    *,
    seed: int,
    total_executions: int,
) -> dict:
    if strategy not in POLICIES:
        raise ValueError(f"Unknown strategy: {strategy}")
    if method not in run_pairs.METHODS:
        raise ValueError(f"Unsupported paired method: {method}")
    if type(total_executions) is not int or total_executions < 0:
        raise ValueError("total_executions must be a nonnegative integer")

    descriptor = run_pairs.METHODS[method]
    executions = 0

    def observe(arguments: tuple[int, ...]) -> bool:
        nonlocal executions
        if executions >= total_executions:
            raise RuntimeError(f"{strategy} exceeded the execution cap for {method}")
        executions += 1
        return run_pairs.execute_candidate(prepared.classes, method, arguments)

    started = time.perf_counter()

    result = _budgeted_search(
        run_pairs.ARITY[descriptor],
        prepared.constants[method] if strategy == "B" else (),
        observe,
        random.Random(seed),
        total_executions,
    )

    elapsed = time.perf_counter() - started

    return {
        "method": method,
        "method_id": f"{run_pairs.CLASS_NAME}.{method}:{descriptor}",
        "strategy": strategy,
        "seed": seed,
        "total_executions": total_executions,
        "oracle": run_pairs.ORACLE,
        **asdict(result),
        "executions": executions,
        "execution_seconds": elapsed,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument(
        "--total-executions",
        type=int,
        required=True,
        help="Maximum executions per method and strategy",
    )
    args = parser.parse_args(argv)

    if args.total_executions < 0:
        parser.error("--total-executions must be nonnegative")

    try:
        with tempfile.TemporaryDirectory(prefix="group15-compare-") as directory:
            prepared = run_pairs.compile_pair_benchmark(Path(directory))

            results = [
                run_arm(
                    prepared,
                    method,
                    strategy,
                    seed=args.seed,
                    total_executions=args.total_executions,
                )
                for method in run_pairs.METHODS
                for strategy in POLICIES
            ]

    except (ValueError, RuntimeError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "oracle": run_pairs.ORACLE,
                "preparation_seconds": prepared.preparation_seconds,
                "timing_note": "Execution times include JVM startup.",
                "results": results,
            },
            indent=2,
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())