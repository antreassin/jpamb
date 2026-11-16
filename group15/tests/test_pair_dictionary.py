"""Integration checks for B's two-method JVM smoke experiment."""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from group15 import run_pairs
from group15.dictionary import extract_javap_constants


@pytest.fixture(scope="module")
def prepared(tmp_path_factory):
    if not all(shutil.which(tool) for tool in ("javac", "java", "javap")):
        pytest.skip("Real JVM smoke tests require a JDK 17+ on PATH")
    return run_pairs.compile_pair_benchmark(tmp_path_factory.mktemp("pair-classes"))


@pytest.fixture
def synthetic_prepared(tmp_path):
    return run_pairs.PreparedBenchmark(
        classes=tmp_path,
        constants={"p03": (0, 1, 100003), "p04": (0, 1, 100003)},
        preparation_seconds=0.5,
    )


def test_real_compilation_extracts_only_selected_method_constants(prepared):
    assert prepared.constants == {"p03": (0, 1, 100003), "p04": (0, 1, 100003)}
    assert prepared.preparation_seconds >= 0
    assert (prepared.classes / "group15" / "PairReachability.class").is_file()


@pytest.mark.parametrize(
    "method,budget,verdict,witness,counts",
    [
        ("p04", 3, "reachable", (100003,), (9, 2, 0)),
        ("p03", 3, "unknown", None, (9, 3, 0)),
        ("p04", 1, "unknown", None, (9, 1, 0)),
    ],
)
def test_dictionary_search_executes_real_java(
    prepared, method, budget, verdict, witness, counts
):
    result = run_pairs.run_experiment(
        prepared, method, seed=15, dictionary_trials=budget, random_trials=0
    )
    assert result["verdict"] == verdict
    assert result["witness"] == witness
    assert (
        tuple(
            result[key]
            for key in ("fixed_trials", "dictionary_trials", "random_trials")
        )
        == counts
    )
    assert result["executions"] == sum(counts)
    assert result["execution_seconds"] >= 0
    assert result["oracle"] == "return-equals-2"


def test_runner_passes_seed_and_budgets_reproducibly(monkeypatch, synthetic_prepared):
    def run(seed):
        seen = []

        def misses(classes, method, arguments):
            seen.append((method, arguments))
            return False

        monkeypatch.setattr(run_pairs, "execute_candidate", misses)
        result = run_pairs.run_experiment(
            synthetic_prepared, "p03", seed=seed, dictionary_trials=1, random_trials=5
        )
        result.pop("execution_seconds")
        return result, seen

    first, seen = run(15)
    assert run(15) == (first, seen)
    assert run(16)[1] != seen
    assert (
        first["fixed_trials"],
        first["dictionary_trials"],
        first["random_trials"],
    ) == (
        9,
        1,
        5,
    )
    assert first["executions"] == len(seen) == 15
    assert first["verdict"] == "unknown"


def test_execution_failure_is_not_reported_as_unknown(monkeypatch, synthetic_prepared):
    def fails(*args):
        raise RuntimeError("JVM execution failed")

    monkeypatch.setattr(run_pairs, "execute_candidate", fails)
    with pytest.raises(RuntimeError, match="JVM execution failed"):
        run_pairs.run_experiment(synthetic_prepared, "p03")


@pytest.mark.parametrize("output", ["", "2\n1\n", "true\n", "3\n", "1.0\n"])
def test_malformed_jvm_output_is_an_error(monkeypatch, tmp_path, output):
    monkeypatch.setattr(run_pairs, "_run", lambda *args, **kwargs: output)
    with pytest.raises(RuntimeError):
        run_pairs.execute_candidate(tmp_path, "p04", (0,))


@pytest.mark.parametrize(
    "error",
    [
        subprocess.CalledProcessError(1, ["javac"], stderr="compilation failed"),
        subprocess.TimeoutExpired(["java"], 5),
        OSError("executable missing"),
    ],
)
def test_process_failures_are_errors(monkeypatch, error):
    def fails(*args, **kwargs):
        raise error

    monkeypatch.setattr(run_pairs.subprocess, "run", fails)
    with pytest.raises(RuntimeError):
        run_pairs._run(["java"])


def test_unsupported_method_is_rejected_before_execution(
    monkeypatch, synthetic_prepared
):
    def unexpected(*args, **kwargs):
        pytest.fail("Unsupported methods must not launch Java")

    monkeypatch.setattr(run_pairs, "_run", unexpected)
    with pytest.raises(ValueError):
        run_pairs.execute_candidate(synthetic_prepared.classes, "p01", (0,))
    with pytest.raises(ValueError):
        run_pairs.run_experiment(synthetic_prepared, "p08")


DISASSEMBLY = """Compiled from "PairReachability.java"
public final class group15.PairReachability {
  public static int p02(int);
    descriptor: (I)I
    Code:
       0: sipush        999
       3: ireturn
    LineNumberTable:
      line 40: 0

  public static int p03(int);
    descriptor: (I)I
    Code:
       0: iconst_0
       1: ldc           #7                  // int 100003
       3: iconst_1
       4: ireturn
    LineNumberTable:
      line 53: 0

  public static int p04(int);
    descriptor: (I)I
    Code:
       0: iconst_1
       1: ireturn
    LineNumberTable:
      line 67: 0
}
"""


def test_disassembly_parser_keeps_method_constants_separate():
    methods = run_pairs.parse_pair_disassembly(DISASSEMBLY)
    assert set(methods) == {"p03", "p04"}
    assert extract_javap_constants(methods["p03"]) == (0, 1, 100003)
    assert extract_javap_constants(methods["p04"]) == (1,)


def test_disassembly_parser_rejects_wrong_descriptor():
    invalid = DISASSEMBLY.replace("descriptor: (I)I", "descriptor: (II)I")
    with pytest.raises(ValueError):
        run_pairs.parse_pair_disassembly(invalid)


def test_disassembly_parser_requires_both_methods_and_debug_lines():
    for invalid in (
        DISASSEMBLY.replace("p04(int)", "p08(int)"),
        DISASSEMBLY.replace("LineNumberTable:", "MissingDebugInformation:"),
        "",
    ):
        with pytest.raises(ValueError):
            run_pairs.parse_pair_disassembly(invalid)
