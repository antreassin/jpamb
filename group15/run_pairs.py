"""Dictionary B smoke experiment for p03 and p04 only.

Run from the repository root with ``python -m group15.run_pairs``.
Constants come exclusively from each compiled method's bytecode; neither source
comments nor targets.json supplies inputs. B's nine fixed inputs precede the
separate dictionary and random trial budgets.

The temporary oracle is return == 2, NOT bytecode-level target tracking or JPAMB
outcome scoring. In these two unchanged, loop-free methods, each flag starts at
zero and is assigned once, with Target 1 before Target 2. Only for that restricted
shape does the return value establish both targets in order in one invocation.
Replace execute_candidate's observation with instruction tracking for the final
analyser. A fresh JVM is launched for every candidate: execution timings include
startup and are NOT comparable to the final two-second benchmark.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from group15.dictionary import MAX_INT, MIN_INT, extract_javap_constants, search

HERE = Path(__file__).resolve().parent
METHODS = ("p03", "p04")
CLASS_NAME = "group15.PairReachability"
ORACLE = "return-equals-2"
TIMING_NOTE = (
    "Preparation includes compilation, disassembly, and constant extraction. "
    "Execution includes B input generation and a fresh JVM launch per candidate. "
    "These smoke-test timings are not comparable to the final two-second benchmark."
)


@dataclass(frozen=True)
class PreparedBenchmark:
    classes: Path
    constants: dict[str, tuple[int, ...]]
    preparation_seconds: float


def _run(command: list[str], *, timeout: float = 60) -> str:
    try:
        completed = subprocess.run(
            command, text=True, capture_output=True, timeout=timeout, check=True
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"Command timed out after {timeout}s: {command[0]}") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"Command failed ({exc.returncode}): {' '.join(command)}\n"
            f"{exc.stdout or ''}{exc.stderr or ''}"
        ) from exc
    except OSError as exc:
        raise RuntimeError(f"Could not launch {command[0]}: {exc}") from exc
    return completed.stdout


def parse_pair_disassembly(text: str) -> dict[str, list[tuple[int, str, str]]]:
    """Read only the two selected method bodies, without mixing other constants."""
    headers = list(
        re.finditer(
            r"^  (?:public|protected|private) [^\n]*;[ \t]*$", text, re.MULTILINE
        )
    )
    methods = {}
    for index, header in enumerate(headers):
        name_match = re.search(r"\b(p03|p04)\(", header.group())
        if name_match is None:
            continue
        name = name_match[1]
        if name in methods:
            raise ValueError(f"Ambiguous compiled method: {name}")
        end = headers[index + 1].start() if index + 1 < len(headers) else len(text)
        body = text[header.end() : end]
        descriptor = re.search(r"^\s*descriptor: (\S+)", body, re.MULTILINE)
        if descriptor is None or descriptor[1] != "(I)I":
            raise ValueError(f"{name}: expected descriptor (I)I")
        if "Code:" not in body or "LineNumberTable:" not in body:
            raise ValueError(f"{name}: missing bytecode or debug line information")
        code = body.split("Code:", 1)[1].split("LineNumberTable:", 1)[0]
        instructions = [
            (int(match[1]), match[2], match[3].strip())
            for match in re.finditer(r"^\s*(\d+):\s+(\S+)([^\n]*)$", code, re.MULTILINE)
        ]
        if not instructions:
            raise ValueError(f"{name}: no bytecode instructions")
        if not re.search(r"\bline \d+: \d+", body.split("LineNumberTable:", 1)[1]):
            raise ValueError(f"{name}: empty debug line table")
        methods[name] = instructions
    if set(methods) != set(METHODS):
        raise ValueError("Disassembly must contain p03 and p04")
    return methods


def compile_pair_benchmark(build_dir: Path) -> PreparedBenchmark:
    """Compile the benchmark and smoke harness into the caller's build directory."""
    started = time.perf_counter()
    for tool in ("javac", "javap", "java"):
        if shutil.which(tool) is None:
            raise RuntimeError(f"{tool} is required; use a JDK 17+ installation")
    classes = Path(build_dir).resolve() / "classes"
    classes.mkdir(parents=True, exist_ok=True)
    _run(
        [
            "javac",
            "-g",
            "--release",
            "17",
            "-d",
            str(classes),
            str(HERE / "src" / "group15" / "PairReachability.java"),
            str(HERE / "validation" / "PairRuntimeCheck.java"),
        ]
    )
    disassembly = _run(
        ["javap", "-classpath", str(classes), "-c", "-l", "-s", CLASS_NAME]
    )
    methods = parse_pair_disassembly(disassembly)
    constants = {name: extract_javap_constants(methods[name]) for name in METHODS}
    return PreparedBenchmark(classes, constants, time.perf_counter() - started)


def execute_candidate(classes: Path, method: str, arguments: tuple[int, ...]) -> bool:
    """Smoke oracle only: run one invocation and check its return value, not PCs."""
    if method not in METHODS:
        raise ValueError("Only p03 and p04 are supported")
    if (
        len(arguments) != 1
        or type(arguments[0]) is not int
        or not MIN_INT <= arguments[0] <= MAX_INT
    ):
        raise ValueError("Expected exactly one signed Java int")
    output = _run(
        [
            "java",
            "-Xint",
            "-cp",
            str(classes),
            "group15.validation.PairRuntimeCheck",
            method,
            str(arguments[0]),
        ],
        timeout=5,
    ).strip()
    if output not in ("0", "1", "2"):
        raise RuntimeError(f"{method}: invalid JVM return output: {output!r}")
    return output == "2"


def run_experiment(
    prepared: PreparedBenchmark,
    method: str,
    *,
    seed: int = 15,
    dictionary_trials: int = 3,
    random_trials: int = 5,
) -> dict:
    if method not in METHODS:
        raise ValueError("Only p03 and p04 are supported")
    constants = prepared.constants[method]
    started = time.perf_counter()
    result = search(
        1,
        constants,
        lambda arguments: execute_candidate(prepared.classes, method, arguments),
        random.Random(seed),
        dictionary_trials=dictionary_trials,
        random_trials=random_trials,
    )
    elapsed = time.perf_counter() - started
    return {
        "method": method,
        "method_id": f"{CLASS_NAME}.{method}:(I)I",
        "constants": constants,
        "seed": seed,
        "dictionary_budget": dictionary_trials,
        "random_budget": random_trials,
        "oracle": ORACLE,
        "verdict": result.verdict,
        "witness": result.witness,
        "fixed_trials": result.fixed_trials,
        "dictionary_trials": result.dictionary_trials,
        "random_trials": result.random_trials,
        "executions": result.fixed_trials
        + result.dictionary_trials
        + result.random_trials,
        "execution_seconds": elapsed,
    }


def _nonnegative(value: str) -> int:
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError("trial budgets must be nonnegative")
    return number


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=15)
    parser.add_argument("--dictionary-trials", type=_nonnegative, default=3)
    parser.add_argument("--random-trials", type=_nonnegative, default=5)
    args = parser.parse_args(argv)
    try:
        # Leave both the single-line validation reports and the workspace untouched.
        with tempfile.TemporaryDirectory(prefix="group15-pairs-") as directory:
            prepared = compile_pair_benchmark(Path(directory))
            results = [
                run_experiment(
                    prepared,
                    method,
                    seed=args.seed,
                    dictionary_trials=args.dictionary_trials,
                    random_trials=args.random_trials,
                )
                for method in METHODS
            ]
        print(
            json.dumps(
                {
                    "oracle": ORACLE,
                    "timing_note": TIMING_NOTE,
                    "preparation_seconds": prepared.preparation_seconds,
                    "results": results,
                },
                indent=2,
            )
        )
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
