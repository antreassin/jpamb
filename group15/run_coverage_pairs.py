from __future__ import annotations

import argparse
import json
import random
import sys
import tempfile
import time
from collections.abc import Iterable, Iterator
from dataclasses import asdict
from itertools import product
from pathlib import Path

from group15 import run_pairs
from group15.coverage_fuzz import fuzz
from group15.dictionary import FIXED_SEEDS, dictionary_inputs
from group15.pair_execution import PairMethod, prepare_pair_methods, trace_candidate


def invocation_counts(statuses, *, detailed):
    counts = {"cutoffs": statuses["step_limit"]}
    if detailed:
        counts.update(
            normal_returns=statuses["returned"],
            exceptional_executions=statuses["exception"],
        )
    return counts


def _run_coverage(
    method: PairMethod,
    seeds: Iterable[tuple[int, ...]],
    *,
    strategy: str,
    seed: int,
    total_executions: int,
    max_steps: int | None = None,
    trace=None,
) -> dict:
    if type(seed) is not int:
        raise ValueError("seed must be an integer")
    if max_steps is None:
        max_steps = len(method.instructions)
    if type(max_steps) is not int or max_steps < 0:
        raise ValueError("max_steps must be a nonnegative integer")
    execute = trace_candidate if trace is None else trace
    statuses = dict.fromkeys(("returned", "step_limit", "exception"), 0)

    def observe(arguments: tuple[int, ...]) -> tuple[frozenset[int], bool]:
        observation = execute(method, arguments, max_steps=max_steps)
        statuses[observation.status] += 1
        return observation.coverage, observation.pair_hit

    started = time.perf_counter()
    result = fuzz(
        seeds,
        observe,
        rng=random.Random(seed),
        total_executions=total_executions,
    )
    elapsed = time.perf_counter() - started
    return {
        "method_id": method.method_id,
        "strategy": strategy,
        "oracle": "ordered-instruction-entries",
        "seed": seed,
        "total_executions": total_executions,
        "max_steps": max_steps,
        "instruction_count": len(method.instructions),
        **asdict(result),
        "executions": result.executions,
        **invocation_counts(statuses, detailed=trace is not None),
        "execution_seconds": elapsed,
    }


def run_c(
    method: PairMethod,
    *,
    seed: int,
    total_executions: int,
    max_steps: int | None = None,
    trace=None,
) -> dict:
    return _run_coverage(
        method,
        product(FIXED_SEEDS, repeat=method.arity),
        strategy="C",
        seed=seed,
        total_executions=total_executions,
        max_steps=max_steps,
        trace=trace,
    )


def run_d(
    method: PairMethod,
    *,
    constants: tuple[int, ...],
    seed: int,
    total_executions: int,
    max_steps: int | None = None,
    trace=None,
) -> dict:
    fixed_size = len(FIXED_SEEDS) ** method.arity

    def seeds() -> Iterator[tuple[int, ...]]:
        yield from product(FIXED_SEEDS, repeat=method.arity)
        yield from dictionary_inputs(
            method.arity, constants, max_trials=max(0, total_executions - fixed_size)
        )

    row = _run_coverage(
        method,
        seeds(),
        strategy="D",
        seed=seed,
        total_executions=total_executions,
        max_steps=max_steps,
        trace=trace,
    )
    # The engine counts both deterministic seed phases in fixed_executions.
    seed_executions = row["fixed_executions"]
    row["fixed_executions"] = min(seed_executions, fixed_size)
    row["dictionary_executions"] = seed_executions - row["fixed_executions"]
    return row


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run coverage-guided testing on paired methods."
    )
    parser.add_argument("--strategy", choices=("C", "D"), default="C")
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--total-executions", type=int, required=True)
    parser.add_argument("--max-steps", type=int)
    args = parser.parse_args(argv)
    if args.total_executions < 0:
        parser.error("--total-executions must be nonnegative")
    if args.max_steps is not None and args.max_steps < 0:
        parser.error("--max-steps must be nonnegative")

    try:
        with tempfile.TemporaryDirectory(prefix="group15-coverage-") as directory:
            started = time.perf_counter()
            prepared = run_pairs.compile_pair_benchmark(
                Path(directory), include_constants=args.strategy == "D"
            )
            methods = prepare_pair_methods(prepared)
            preparation_seconds = time.perf_counter() - started
            options = {
                "seed": args.seed,
                "total_executions": args.total_executions,
                "max_steps": args.max_steps,
            }
            if args.strategy == "D":
                results = [
                    run_d(method, constants=prepared.constants[name], **options)
                    for name, method in methods.items()
                ]
            else:
                results = [run_c(method, **options) for method in methods.values()]
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    report = {"preparation_seconds": preparation_seconds, "results": results}
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
