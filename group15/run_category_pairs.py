from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path
from time import perf_counter

from group15 import category_backend as backend
from group15 import validate
from group15.run_pair_experiments import STRATEGIES, run_trial

OUTPUT = Path(__file__).resolve().parent / "build" / "category-evaluation"
CLASS_NAME = "group15.LineReachabilityCategories"
DATASET_REVISION = "a487444cb33f99277acf2f5110f022e295c69bb2"


def run_searches(suite, strategies, *, seed, total_executions, max_steps):
    rows = []
    for query in suite.queries:
        name = query["method"]
        identity = {
            "id": query["id"],
            "category": query["category"],
            "method_id": query["method_id"],
        }
        for strategy in strategies:
            if name in suite.unsupported:
                row = {
                    "strategy": strategy,
                    "seed": seed,
                    "total_executions": total_executions,
                    "max_steps": max_steps,
                    "verdict": "unsupported",
                    "reason": suite.unsupported[name],
                    "witness": None,
                    "executions": 0,
                    "search_seconds": 0.0,
                }
            else:
                row = run_trial(
                    suite.methods[name],
                    strategy,
                    seed=seed,
                    total_executions=total_executions,
                    max_steps=max_steps,
                    trace=suite.trace,
                    constants=suite.constants[name] if strategy in ("B", "D") else None,
                )
            rows.append({**identity, **row})
    return rows


def load_labels(source: Path) -> dict[str, bool]:
    labels = {}
    for name, label in re.findall(
        r"^[ \t]*// (\w+_\d{2}): (REACHABLE|UNREACHABLE) pair[ \t]*$",
        source.read_text(encoding="utf-8"),
        re.MULTILINE,
    ):
        if name in labels:
            raise ValueError(f"Duplicate declared label for {name}")
        labels[name] = label == "REACHABLE"
    return labels


def _ordered(events):
    path = iter(events)
    return "T1" in path and "T2" in path


def replay_witnesses(suite, rows, build: Path):
    witnesses = sorted(
        {
            (r["method_id"], tuple(r["witness"]))
            for r in rows
            if r["verdict"] == "reachable"
        }
    )
    if not witnesses:
        return []
    names = {q["method_id"]: q["method"] for q in suite.queries}
    source = suite.source.read_bytes()
    if hashlib.sha256(source).hexdigest() != suite.fingerprints["source_sha256"]:
        raise ValueError("Category source changed before JVM replay")
    header = "public final class LineReachabilityCategories {"
    marked, count = re.subn(
        r"= 1;[ \t]*// Target ([12])[ \t]*$",
        r"= pilotMark(\1);",
        source.decode("utf-8"),
        flags=re.MULTILINE,
    )
    if count != 2 * len(suite.queries) or marked.count(header) != 1:
        raise ValueError("Unexpected category source markers for JVM replay")
    marked = marked.replace(
        header,
        header
        + '\n    private static int pilotMark(int t) { System.out.println("T" + t); return 1; }',
    )
    build.mkdir(parents=True, exist_ok=True)
    copy = build / suite.source.name
    copy.write_text(marked, encoding="utf-8")
    validate.run(
        [
            "javac",
            "-g",
            "--release",
            "17",
            "-proc:none",
            "-d",
            build,
            copy,
            suite.harness,
        ]
    )

    def invoke(classes, request):
        return validate.run(
            [
                "java",
                "-Xint",
                "-cp",
                classes,
                "group15.validation.RuntimeCheck",
                CLASS_NAME,
            ],
            input=request,
        ).splitlines()

    replays = []
    for method, args in witnesses:
        request = " ".join([names[method], *map(str, args)]) + "\n"
        original = invoke(suite.classes, request)
        diagnostic = invoke(build, request)
        events = diagnostic[:-1]
        if (
            original != ["2"]
            or diagnostic[-1:] != original
            or any(e not in ("T1", "T2") for e in events)
            or not _ordered(events)
        ):
            raise RuntimeError(
                f"JVM replay mismatch for {method}{args}: {original}, {diagnostic}"
            )
        replays.append(
            {"method_id": method, "witness": args, "events": events, "return_value": 2}
        )
    return replays


def score(rows, labels, replays):
    verified = {
        (r["method_id"], tuple(r["witness"]))
        for r in replays
        if _ordered(r["events"]) and r["return_value"] == 2
    }
    hits = {
        (r["method_id"], tuple(r["witness"]))
        for r in rows
        if r["verdict"] == "reachable"
    }
    if hits != verified:
        raise ValueError("Discovered witnesses and JVM evidence differ")
    groups = defaultdict(list)
    disagreements = []
    for row in rows:
        if row["verdict"] not in ("reachable", "unknown", "unsupported"):
            raise ValueError(f"Invalid dynamic verdict for {row['id']}")
        if row["verdict"] == "reachable" and not labels[row["id"]]:
            disagreements.append(
                {k: row[k] for k in ("id", "method_id", "strategy", "witness")}
            )
        groups[row["category"], row["strategy"]].append(row)
    categories = []
    for (category, strategy), group in groups.items():
        categories.append(
            {
                "category": category,
                "strategy": strategy,
                "queries": len(group),
                **{
                    v: sum(r["verdict"] == v for r in group)
                    for v in ("reachable", "unknown", "unsupported")
                },
                "disagreements": sum(
                    r["verdict"] == "reachable" and not labels[r["id"]] for r in group
                ),
                "unknown_feasible": sum(
                    r["verdict"] == "unknown" and labels[r["id"]] for r in group
                ),
                **{
                    key: sum(r.get(key, 0) for r in group)
                    for key in (
                        "executions",
                        "normal_returns",
                        "cutoffs",
                        "exceptional_executions",
                        "search_seconds",
                    )
                },
            }
        )
    return {"categories": categories, "disagreements": disagreements}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the categorised paired-target pilot with local pinned dependencies."
    )
    parser.add_argument(
        "--deps",
        type=Path,
        default=backend.DEFAULT_DEPS,
        help="Local dependency root with the original repo-relative paths",
    )
    parser.add_argument(
        "--list-dependencies",
        action="store_true",
        help="Print pinned GitHub API paths and SHA-256 digests for offline provisioning",
    )
    parser.add_argument(
        "--strategies", nargs="+", choices=STRATEGIES, default=("B", "C", "D")
    )
    parser.add_argument("--seed", type=int, default=15)
    parser.add_argument("--total-executions", type=int, default=256)
    parser.add_argument("--max-steps", type=int, default=10000)
    args = parser.parse_args(argv)
    if args.list_dependencies:
        print(
            json.dumps(
                {
                    path: {
                        "sha256": digest,
                        "url": f"https://api.github.com/repos/antreassin/jpamb/contents/{path}?ref={backend.REVISION}",
                    }
                    for path, digest in backend.PINNED_FILES.items()
                },
                indent=2,
            )
        )
        return 0
    if (
        len(set(args.strategies)) != len(args.strategies)
        or min(args.total_executions, args.max_steps) < 0
    ):
        parser.error("Select distinct strategies and nonnegative bounds")
    try:
        OUTPUT.mkdir(parents=True, exist_ok=True)
        lock = OUTPUT / ".running"
        with lock.open("x"):
            pass
        try:
            return _pilot(args)
        finally:
            lock.unlink(missing_ok=True)
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print(f"Category evaluation failed: {exc}", file=sys.stderr)
        return 1


def _pilot(args):
    summary_path = OUTPUT / "summary.json"
    summary_path.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory(dir=OUTPUT) as directory:
        work = Path(directory)
        suite = backend.prepare_categories(
            args.deps,
            work / "benchmark",
            include_constants=bool({"B", "D"}.intersection(args.strategies)),
        )
        rows = run_searches(
            suite,
            args.strategies,
            seed=args.seed,
            total_executions=args.total_executions,
            max_steps=args.max_steps,
        )
        raw = work / "trials.jsonl"
        with raw.open("w", encoding="utf-8") as stream:
            for row in rows:
                stream.write(json.dumps(row) + "\n")
        raw.replace(OUTPUT / raw.name)
        started = perf_counter()
        replays = replay_witnesses(suite, rows, work / "replay")
        replay_seconds = perf_counter() - started
        labels = load_labels(suite.source)
        if labels.keys() != {q["id"] for q in suite.queries}:
            raise ValueError("Labels do not match the category query inventory")
        scores = score(rows, labels, replays)
        report = {
            "schema_version": 1,
            "suite_id": "group15-categories-pairs-v1",
            "status": "label_disagreement" if scores["disagreements"] else "verified",
            "dependency_repository": "antreassin/jpamb",
            "simone_revision": backend.REVISION,
            "georgios_revision": DATASET_REVISION,
            "fingerprints": suite.fingerprints,
            "environment": {
                "python": platform.python_version(),
                "java": validate.run(["java", "--version"]).strip(),
                "platform": platform.platform(),
            },
            "seed": args.seed,
            "total_executions": args.total_executions,
            "max_steps": args.max_steps,
            "strategies": args.strategies,
            "query_count": len(suite.queries),
            "supported": len(suite.methods),
            "unsupported": suite.unsupported,
            "preparation_seconds": suite.preparation_seconds,
            "constant_extraction_seconds": suite.constant_extraction_seconds,
            "replay_seconds": replay_seconds,
            "replays": replays,
            **scores,
        }
        pending = work / summary_path.name
        pending.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        pending.replace(summary_path)
    print(
        f"{len(rows)} rows, {len(suite.methods)} supported queries, {len(replays)} distinct witnesses replayed"
    )
    if scores["disagreements"]:
        print(f"Investigate label disagreements in {summary_path}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
