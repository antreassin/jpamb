"""Run A with fresh randomness by default; --seed replays a recorded run."""

import argparse
import json
import platform
import random
import secrets
import subprocess
import sys
from collections import Counter

from analysis_common import (
    load_inputs,
    prepare_queries,
    query_metadata,
    report_metadata,
)
from basic_search import DEFAULT_RANDOM_TRIALS, FIXED_SEEDS, search
from validate import BUILD, ROOT, digest, execute_bytecode


def analyse(inputs: dict, disassembly: str, seed: int,
            random_trials: int = DEFAULT_RANDOM_TRIALS) -> list[dict]:
    if type(seed) is not int:
        raise ValueError("seed must be an integer")
    rng = random.Random(seed)
    results = []
    for query, method, _ in prepare_queries(inputs, disassembly):
        arity = 1 if method["descriptor"] == "(I)I" else 2
        result = search(
            arity,
            # Observe target entry, not the method's return value.
            lambda arguments, method=method: execute_bytecode(method, arguments)[1],
            rng,
            random_trials,
        )
        results.append({
            **query_metadata(query, method),
            "verdict": result.verdict,
            "witness": list(result.witness) if result.witness is not None else None,
            "fixed_trials": result.fixed_trials,
            "random_trials": result.random_trials,
            "witness_phase": (
                None if result.witness is None else "random" if result.random_trials else "fixed"
            ),
        })
    return results


def nonnegative_int(value: str) -> int:
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError("must be nonnegative")
    return number


def main(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, help="replay seed (default: a fresh 64-bit seed)")
    parser.add_argument("--random-trials", type=nonnegative_int, default=DEFAULT_RANDOM_TRIALS,
                        help="maximum random trials per query after fixed seeds (default: 1000)")
    args = parser.parse_args(argv)
    output = BUILD / "a-results.json"
    output.unlink(missing_ok=True)
    seed = secrets.randbits(64) if args.seed is None else args.seed
    inputs, disassembly = load_inputs(BUILD)
    results = analyse(inputs, disassembly, seed, args.random_trials)
    summary = {value: 0 for value in ("reachable", "unknown")}
    summary.update(Counter(result["verdict"] for result in results))
    report = {
        **report_metadata(inputs, BUILD),
        "analysis": "A",
        "backend": "javap with group15.validate.execute_bytecode",
        "runner_sha256": digest(ROOT / "group15" / "run_a.py"),
        "basic_sha256": digest(ROOT / "solutions" / "syntactic" / "src" / "basic_search.py"),
        "python_version": platform.python_version(),
        "seed": seed,
        "fixed_seeds": list(FIXED_SEEDS),
        "random_trials_per_query": args.random_trials,
        "random_distribution": "independent uniform signed 32-bit integers, with replacement",
        "summary": summary,
        "queries": results,
    }
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    for result in results:
        print(f"{result['id']};{result['verdict']};witness={result['witness']}")
    print(f"A: {len(results)} queries; {summary['reachable']} reachable; {summary['unknown']} unknown")
    print(f"Seed: {seed}")
    print(f"Report: {output}")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, IndexError, TypeError, OSError, subprocess.TimeoutExpired) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
