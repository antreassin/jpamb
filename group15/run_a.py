"""Run A on paired targets (Categories by default); --seed replays a run."""

import argparse
import json
import platform
import secrets
import subprocess
import sys
from collections import Counter

from analysis_common import load_inputs, report_metadata
from basic_search import DEFAULT_RANDOM_TRIALS, FIXED_SEEDS, MAX_STEPS, analyse
from validate import BUILD, ROOT, digest
from pair_dataset import add_dataset_argument


def nonnegative_int(value: str) -> int:
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError("must be nonnegative")
    return number


def main(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description=__doc__)
    add_dataset_argument(parser)
    parser.add_argument("--seed", type=int, help="replay seed (default: a fresh 64-bit seed)")
    parser.add_argument("--random-trials", type=nonnegative_int, default=DEFAULT_RANDOM_TRIALS,
                        help="maximum random trials per query after fixed seeds (default: 1000)")
    args = parser.parse_args(argv)
    build = BUILD / args.dataset
    output = build / "a-results.json"
    output.unlink(missing_ok=True)
    seed = secrets.randbits(64) if args.seed is None else args.seed
    inputs, disassembly = load_inputs(build)
    results = analyse(inputs, disassembly, seed, args.random_trials)
    summary = {value: 0 for value in ("reachable", "unknown")}
    summary.update(Counter(result["verdict"] for result in results))
    report = {
        **report_metadata(inputs, build),
        "analysis": "A",
        "backend": "javap with group15.validate.execute_bytecode",
        "runner_sha256": digest(ROOT / "group15" / "run_a.py"),
        "basic_sha256": digest(ROOT / "solutions" / "syntactic" / "src" / "basic_search.py"),
        "python_version": platform.python_version(),
        "seed": seed,
        "fixed_seeds": list(FIXED_SEEDS),
        "random_trials_per_query": args.random_trials,
        "random_distribution": "independent uniform signed 32-bit integers, with replacement",
        **({"max_steps_per_trial": MAX_STEPS} if inputs["schema_version"] == 2 else {}),
        "summary": summary,
        "queries": results,
    }
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    for result in results:
        reason = f";reason={result['reason']}" if "reason" in result else ""
        print(f"{result['id']};{result['verdict']};witness={result['witness']}{reason}")
    print(f"A: {len(results)} queries; {summary['reachable']} reachable; "
          f"{summary['unknown']} unknown; {summary.get('unsupported', 0)} unsupported")
    print(f"Seed: {seed}")
    print(f"Report: {output}")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, IndexError, TypeError, OSError, subprocess.TimeoutExpired) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
