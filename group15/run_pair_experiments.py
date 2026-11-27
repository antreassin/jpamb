from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from time import perf_counter

from group15 import run_pairs, validate
from group15.compare_pairs import budgeted_search
from group15.dictionary import extract_javap_constants
from group15.pair_execution import PairMethod, prepare_pair_methods, trace_candidate
from group15.run_coverage_pairs import invocation_counts, run_c, run_d

STRATEGIES = ("A", "B", "C", "D")


@dataclass(frozen=True)
class PreparedSuite:
    benchmark: run_pairs.PreparedBenchmark
    methods: dict[str, PairMethod]
    preparation_seconds: float
    constant_extraction_seconds: float


def prepare_suite(
    build_dir: Path, strategies: Sequence[str] = STRATEGIES
) -> PreparedSuite:
    selected = set(strategies)
    if not selected or not selected.issubset(STRATEGIES):
        raise ValueError("Select one or more strategies from A, B, C, D")
    if len(selected) != len(strategies):
        raise ValueError("Each strategy may be selected only once")

    started = perf_counter()
    benchmark = run_pairs.compile_pair_benchmark(build_dir, include_constants=False)
    methods = prepare_pair_methods(benchmark)
    preparation_seconds = perf_counter() - started
    extraction_seconds = 0.0
    if "B" in strategies or "D" in strategies:
        started = perf_counter()
        constants = {
            name: extract_javap_constants(method.instructions)
            for name, method in methods.items()
        }
        extraction_seconds = perf_counter() - started
        benchmark = replace(benchmark, constants=constants)
    return PreparedSuite(benchmark, methods, preparation_seconds, extraction_seconds)


def _run_ab(method, constants, *, seed, total_executions, max_steps, trace=None):
    covered = set()
    executions = 0
    execute = trace_candidate if trace is None else trace
    statuses = dict.fromkeys(("returned", "step_limit", "exception"), 0)

    def observe(arguments):
        nonlocal executions
        if executions >= total_executions:
            raise RuntimeError("Candidate execution budget exceeded")
        executions += 1
        observation = execute(method, arguments, max_steps=max_steps)
        covered.update(observation.coverage)
        statuses[observation.status] += 1
        return observation.pair_hit

    result = budgeted_search(
        method.arity, constants, observe, random.Random(seed), total_executions
    )
    return {
        "verdict": result.verdict,
        "witness": result.witness,
        "fixed_executions": result.fixed_trials,
        "dictionary_executions": result.dictionary_trials,
        "random_executions": result.random_trials,
        "executions": executions,
        **invocation_counts(statuses, detailed=trace is not None),
        "covered_instructions": len(covered),
        "corpus_size": None,
    }


def run_trial(
    method: PairMethod,
    strategy: str,
    *,
    seed: int,
    total_executions: int,
    max_steps: int | None = None,
    constants: tuple[int, ...] | None = None,
    trace=None,
) -> dict:
    if strategy not in STRATEGIES:
        raise ValueError(f"Unknown strategy: {strategy}")
    if type(seed) is not int:
        raise ValueError("seed must be an integer")
    if type(total_executions) is not int or total_executions < 0:
        raise ValueError("total_executions must be a nonnegative integer")
    if max_steps is None:
        max_steps = len(method.instructions)
    if type(max_steps) is not int or max_steps < 0:
        raise ValueError("max_steps must be a nonnegative integer")
    if strategy in ("B", "D") and constants is None:
        raise ValueError(f"{strategy} requires the selected method's constants")

    options = {
        "seed": seed,
        "total_executions": total_executions,
        "max_steps": max_steps,
    }
    started = perf_counter()
    if strategy in ("A", "B"):
        row = _run_ab(
            method, constants if strategy == "B" else (), trace=trace, **options
        )
    elif strategy == "C":
        row = run_c(method, trace=trace, **options)
    else:
        row = run_d(method, constants=constants, trace=trace, **options)
    search_seconds = perf_counter() - started

    if row["verdict"] == "reachable":
        termination = "ordered_hit"
    elif row["executions"] == total_executions:
        termination = "budget_exhausted"
    else:
        termination = "empty_corpus"
    result = {
        "method_id": method.method_id,
        "strategy": strategy,
        "oracle": "ordered-instruction-entries",
        **options,
        "verdict": row["verdict"],
        "witness": row["witness"],
        "termination": termination,
        "executions": row["executions"],
        "fixed_executions": row["fixed_executions"],
        "dictionary_executions": row.get("dictionary_executions", 0),
        "random_executions": row.get("random_executions", 0),
        "mutation_executions": row.get("mutation_executions", 0),
        "cutoffs": row["cutoffs"],
        "covered_instructions": row["covered_instructions"],
        "instruction_count": len(method.instructions),
        "corpus_size": row["corpus_size"],
        "search_seconds": search_seconds,
    }
    if trace is not None:
        result["normal_returns"] = row["normal_returns"]
        result["exceptional_executions"] = row["exceptional_executions"]
    return result


def replay_witnesses(suite: PreparedSuite, rows: list[dict]) -> list[dict]:
    witnesses = sorted(
        {
            (r["method_id"], tuple(r["witness"]))
            for r in rows
            if r["verdict"] == "reachable"
        }
    )
    if not witnesses:
        return []
    names = {method.method_id: name for name, method in suite.methods.items()}
    source = run_pairs.PAIR_SOURCE.read_bytes()
    if hashlib.sha256(source).hexdigest() != suite.benchmark.source_sha256:
        raise ValueError("Pair source changed before JVM replay")
    diagnostic, count = re.subn(
        r"//[ \t]*Target ([12])[ \t]*\r?$",
        r'System.out.println("T\1");',
        source.decode("utf-8"),
        flags=re.MULTILINE,
    )
    if count != 2 * len(suite.benchmark.methods):
        raise ValueError("JVM replay requires both source markers for every method")

    replays = []
    with tempfile.TemporaryDirectory(prefix="group15-replay-") as directory:
        copy = Path(directory) / run_pairs.PAIR_SOURCE.name
        copy.write_text(diagnostic, encoding="utf-8")
        validate.run(
            [
                "javac",
                "-g",
                "--release",
                "17",
                "-d",
                directory,
                copy,
                run_pairs.HERE / "validation" / "PairRuntimeCheck.java",
            ]
        )
        for method_id, witness in witnesses:
            name = names[method_id]
            if not run_pairs.execute_candidate(suite.benchmark.classes, name, witness):
                raise RuntimeError(f"Original JVM rejected {name}{witness}")
            output = validate.run(
                [
                    "java",
                    "-Xint",
                    "-cp",
                    directory,
                    "group15.validation.PairRuntimeCheck",
                    name,
                    *map(str, witness),
                ]
            ).splitlines()
            if output != ["T1", "T2", "2"]:
                raise RuntimeError(f"JVM replay mismatch for {name}{witness}: {output}")
            replays.append(
                {
                    "method_id": method_id,
                    "witness": witness,
                    "events": output[:-1],
                    "return_value": int(output[-1]),
                }
            )
    return replays


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run paired reachability experiments with instruction tracing."
    )
    parser.add_argument(
        "--strategies", choices=STRATEGIES, nargs="+", default=STRATEGIES
    )
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--total-executions", type=int, required=True)
    parser.add_argument("--max-steps", type=int)
    args = parser.parse_args(argv)
    if args.total_executions < 0 or (args.max_steps is not None and args.max_steps < 0):
        parser.error("Execution and step bounds must be nonnegative")

    try:
        with tempfile.TemporaryDirectory(prefix="group15-experiment-") as directory:
            suite = prepare_suite(Path(directory), args.strategies)
            rows = [
                run_trial(
                    method,
                    strategy,
                    seed=args.seed,
                    total_executions=args.total_executions,
                    max_steps=args.max_steps,
                    constants=suite.benchmark.constants[name]
                    if strategy in ("B", "D")
                    else None,
                )
                for name, method in suite.methods.items()
                for strategy in args.strategies
            ]
            started = perf_counter()
            replays = replay_witnesses(suite, rows)
            replay_seconds = perf_counter() - started
    except (ValueError, RuntimeError, OSError, subprocess.TimeoutExpired) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    report = {
        "schema_version": 1,
        "source_sha256": suite.benchmark.source_sha256,
        "preparation_seconds": suite.preparation_seconds,
        "constant_extraction_seconds": suite.constant_extraction_seconds,
        "replay_seconds": replay_seconds,
        "results": rows,
        "replays": replays,
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
