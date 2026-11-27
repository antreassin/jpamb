from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median, quantiles
from time import perf_counter

from group15 import run_pairs, validate
from group15.run_pair_experiments import (
    STRATEGIES,
    PreparedSuite,
    prepare_suite,
    replay_witnesses,
    run_trial,
)

BUILD = run_pairs.HERE / "build"
SEEDS = tuple(range(20))
BUDGETS = (16, 64, 128, 256, 1024)
COUNTS = (
    "executions",
    "fixed_executions",
    "dictionary_executions",
    "random_executions",
    "mutation_executions",
    "cutoffs",
)


def run_grid(suite: PreparedSuite, seeds=SEEDS, budgets=BUDGETS):
    for seed in seeds:
        offset = seed % len(STRATEGIES)
        order = STRATEGIES[offset:] + STRATEGIES[:offset]
        for budget in budgets:
            for name, method in suite.methods.items():
                for strategy in order:
                    yield run_trial(
                        method,
                        strategy,
                        seed=seed,
                        total_executions=budget,
                        constants=suite.benchmark.constants[name]
                        if strategy in ("B", "D")
                        else None,
                    )


def load_labels(suite: PreparedSuite) -> dict[str, bool]:
    manifest = json.loads(
        (run_pairs.HERE / "pair-targets.json").read_text(encoding="utf-8")
    )
    if manifest["source_sha256"] != suite.benchmark.source_sha256:
        raise ValueError(
            "Ground-truth source fingerprint differs from the prepared benchmark"
        )
    labels = {}
    for query in manifest["queries"]:
        method_id = f"{run_pairs.CLASS_NAME}.{query['method']}:{query['descriptor']}"
        if method_id in labels or type(query["feasible"]) is not bool:
            raise ValueError(f"Invalid or duplicate feasibility label for {method_id}")
        labels[method_id] = query["feasible"]
    if labels.keys() != {method.method_id for method in suite.methods.values()}:
        raise ValueError("Ground-truth methods differ from the prepared methods")
    return labels


def _statistics(values):
    if not values:
        return {"n": 0, "median": None, "q1": None, "q3": None}
    q1, _, q3 = quantiles(values, n=4, method="inclusive")
    return {"n": len(values), "median": median(values), "q1": q1, "q3": q3}


def _group(rows, labels):
    feasible = [row for row in rows if labels[row["method_id"]]]
    hits = [row for row in feasible if row["verdict"] == "reachable"]
    unknown = sum(row["verdict"] == "unknown" for row in rows)
    missed = len(feasible) - len(hits)
    return {
        "trials": len(rows),
        "feasible_trials": len(feasible),
        "discoveries": len(hits),
        "discovery_rate": len(hits) / len(feasible) if feasible else None,
        "methods_discovered": sorted({r["method_id"] for r in hits}),
        "unknown": unknown,
        "unknown_feasible": missed,
        "unknown_infeasible": unknown - missed,
        "incorrect": len(rows) - unknown - len(hits),
        "executions_to_witness": _statistics([r["executions"] for r in hits]),
        "coverage_fraction": _statistics(
            [r["covered_instructions"] / r["instruction_count"] for r in rows]
        ),
        "search_seconds": _statistics([r["search_seconds"] for r in rows]),
        **{key: sum(r[key] for r in rows) for key in COUNTS},
    }


def summarise(rows, labels, replays):
    by_strategy = defaultdict(list)
    by_method = defaultdict(list)
    discoveries = Counter()
    for row in rows:
        method, strategy, budget = (
            row["method_id"],
            row["strategy"],
            row["total_executions"],
        )
        if row["verdict"] == "reachable" and row["witness"] is not None:
            discoveries[method, tuple(row["witness"])] += 1
        elif row["verdict"] != "unknown" or row["witness"] is not None:
            raise ValueError(f"Invalid search verdict or witness for {method}")
        by_strategy[strategy, budget].append(row)
        by_method[method, strategy, budget].append(row)

    verified = set()
    for replay in replays:
        witness = (replay["method_id"], tuple(replay["witness"]))
        value = replay.get("return_value")
        if replay.get("events") != ["T1", "T2"] or type(value) is not int or value != 2:
            raise ValueError(f"Invalid JVM replay evidence for {witness}")
        verified.add(witness)
    if verified != discoveries.keys():
        raise ValueError("JVM replay evidence differs from the discovered witnesses")
    return {
        "by_strategy_budget": [
            {"strategy": strategy, "total_executions": budget, **_group(group, labels)}
            for (strategy, budget), group in sorted(by_strategy.items())
        ],
        "by_method_strategy_budget": [
            {
                "method_id": method,
                "strategy": strategy,
                "total_executions": budget,
                **_group(group, labels),
            }
            for (method, strategy, budget), group in sorted(by_method.items())
        ],
        "disagreements": [
            {
                "method_id": method,
                "witness": list(witness),
                "feasible": False,
                "jvm_ordered_hit": True,
                "trials": count,
            }
            for (method, witness), count in sorted(discoveries.items())
            if not labels[method]
        ],
    }


def evaluate(output_dir: Path, *, seeds=SEEDS, budgets=BUDGETS) -> dict:
    output_dir = output_dir.resolve()
    if not output_dir.is_relative_to(BUILD.resolve()):
        raise ValueError(f"Evaluation output must be under {BUILD}")
    output_dir.mkdir(parents=True, exist_ok=True)
    lock = output_dir / ".running"
    with lock.open("x"):
        pass
    try:
        summary_path = output_dir / "summary.json"
        summary_path.unlink(missing_ok=True)
        with tempfile.TemporaryDirectory(dir=output_dir) as directory:
            work = Path(directory)
            suite = prepare_suite(work)
            rows = []
            raw_path = work / "trials.jsonl"
            with raw_path.open("w", encoding="utf-8") as raw:
                for row in run_grid(suite, seeds, budgets):
                    rows.append(row)
                    raw.write(json.dumps(row) + "\n")
            raw_path.replace(output_dir / raw_path.name)

            started = perf_counter()
            replays = replay_witnesses(suite, rows)
            replay_seconds = perf_counter() - started
            scores = summarise(rows, load_labels(suite), replays)
            summary = {
                "schema_version": 1,
                "status": "label_disagreement"
                if scores["disagreements"]
                else "verified",
                "source_sha256": suite.benchmark.source_sha256,
                "environment": {
                    "python_version": platform.python_version(),
                    "java_version": validate.run(["java", "--version"]).strip(),
                    "platform": platform.platform(),
                },
                "seeds": list(seeds),
                "budgets": list(budgets),
                "strategies": list(STRATEGIES),
                "strategy_rotation": "seed % 4",
                "max_steps_by_method": {
                    m.method_id: len(m.instructions) for m in suite.methods.values()
                },
                "trial_count": len(rows),
                "preparation_seconds": suite.preparation_seconds,
                "constant_extraction_seconds": suite.constant_extraction_seconds,
                "replay_seconds": replay_seconds,
                "replays": replays,
                **scores,
            }
            pending = work / "summary.json"
            pending.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
            pending.replace(summary_path)
            return summary
    finally:
        lock.unlink()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate the four paired reachability strategies."
    )
    parser.add_argument("--output-dir", type=Path, default=BUILD / "pair-evaluation")
    args = parser.parse_args(argv)
    try:
        summary = evaluate(args.output_dir)
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
        print(f"Evaluation failed: {exc}", file=sys.stderr)
        return 1
    print(
        f"{summary['trial_count']} trials, {len(summary['replays'])} distinct JVM replays"
    )
    if summary["disagreements"]:
        print(
            f"Investigate ground-truth disagreements in {args.output_dir / 'summary.json'}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
