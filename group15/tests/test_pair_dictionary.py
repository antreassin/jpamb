"""Dictionary B experiments and independent validation of the eight pair cases."""

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from group15 import run_pairs
from group15.dictionary import extract_javap_constants

SOURCE = ROOT / "group15/src/group15/PairReachability.java"
DESCRIPTORS = {f"p{i:02d}": "(II)I" if i in (6, 8) else "(I)I" for i in range(1, 9)}


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
    assert prepared.constants == {
        "p01": (0, 1),
        "p02": (0, 1, 5, 10),
        "p03": (0, 1, 100003),
        "p04": (0, 1, 100003),
        "p05": (0, 1),
        "p06": (0, 1),
        "p07": (0, 1),
        "p08": (0, 1, 100003),
    }
    assert prepared.preparation_seconds >= 0
    assert (prepared.classes / "group15" / "PairReachability.class").is_file()


@pytest.mark.parametrize(
    "method,budget,verdict,witness,counts",
    [
        ("p04", 3, "reachable", (100003,), (9, 2, 0)),
        ("p03", 3, "unknown", None, (9, 3, 0)),
        ("p04", 1, "unknown", None, (9, 1, 0)),
        ("p01", 64, "unknown", None, (9, 0, 0)),
        ("p02", 64, "reachable", (6,), (9, 3, 0)),
        ("p05", 64, "unknown", None, (9, 0, 0)),
        ("p06", 64, "reachable", (0, 1), (2, 0, 0)),
        ("p07", 64, "unknown", None, (9, 0, 0)),
        ("p08", 64, "reachable", (100003, 100003), (81, 50, 0)),
        ("p08", 3, "unknown", None, (81, 3, 0)),
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
        result["method_id"]
        == f"group15.PairReachability.{method}:{DESCRIPTORS[method]}"
    )
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
        run_pairs.execute_candidate(synthetic_prepared.classes, "p09", (0,))
    with pytest.raises(ValueError):
        run_pairs.run_experiment(synthetic_prepared, "p09")


@pytest.mark.parametrize(
    "method,arguments",
    [
        ("p01", ()),
        ("p03", (0, 1)),
        ("p06", (0,)),
        ("p08", (0, 1, 2)),
        ("p06", (0, True)),
        ("p06", (-(2**31) - 1, 0)),
        ("p08", (0, 2**31)),
    ],
)
def test_invalid_java_arguments_are_rejected_before_execution(
    tmp_path, monkeypatch, method, arguments
):
    def unexpected(*args, **kwargs):
        pytest.fail("Invalid arguments must not launch Java")

    monkeypatch.setattr(run_pairs, "_run", unexpected)
    with pytest.raises(ValueError):
        run_pairs.execute_candidate(tmp_path, method, arguments)


def _disassembly():
    # Distinct method constants expose accidental leakage from adjacent bodies.
    bodies = []
    for number, (name, descriptor) in enumerate(DESCRIPTORS.items(), start=1):
        params = "int, int" if descriptor == "(II)I" else "int"
        bodies.append(f"""  public static int {name}({params});
    descriptor: {descriptor}
    Code:
       0: bipush {number}
       2: ireturn
    LineNumberTable:
      line {number + 100}: 0
""")
    return "public final class group15.PairReachability {\n" + "".join(bodies) + "}\n"


def test_disassembly_parser_keeps_method_constants_separate():
    methods = run_pairs.parse_pair_disassembly(_disassembly())
    assert set(methods) == set(DESCRIPTORS)
    for number, name in enumerate(DESCRIPTORS, start=1):
        assert extract_javap_constants(methods[name]) == (number,)


@pytest.mark.parametrize("original,wrong", [("(I)I", "(II)I"), ("(II)I", "(I)I")])
def test_disassembly_parser_rejects_wrong_descriptor(original, wrong):
    invalid = _disassembly().replace(
        f"descriptor: {original}", f"descriptor: {wrong}", 1
    )
    with pytest.raises(ValueError):
        run_pairs.parse_pair_disassembly(invalid)


def test_disassembly_parser_requires_all_methods_and_debug_lines():
    text = _disassembly()
    for invalid in (
        text.replace("p04(int)", "p09(int)"),
        text.replace("p04(int)", "p03(int)"),
        text.replace("LineNumberTable:", "MissingDebugInformation:"),
        "",
    ):
        with pytest.raises(ValueError):
            run_pairs.parse_pair_disassembly(invalid)


@pytest.fixture(scope="module")
def ground_truth():
    manifest = json.loads((ROOT / "group15/pair-targets.json").read_text())
    assert ROOT / manifest["source_file"] == SOURCE
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == manifest["source_sha256"]
    queries = {q["method"]: q for q in manifest["queries"]}
    assert set(queries) == set(DESCRIPTORS)
    assert len(manifest["queries"]) == len(queries)
    source = SOURCE.read_text().splitlines()
    for method, query in queries.items():
        assert query["descriptor"] == DESCRIPTORS[method]
        assert query["rationale"].strip()
        assert type(query["feasible"]) is bool
        assert query["feasible"] == (query["pair_witness"] is not None)
        arity = 2 if query["descriptor"] == "(II)I" else 1
        assert len(query["target_witnesses"]) == 2
        witnesses = list(query["target_witnesses"])
        if query["feasible"]:
            witnesses.append(query["pair_witness"])
        for witness in witnesses:
            assert len(witness) == arity
            assert all(type(x) is int and -(2**31) <= x < 2**31 for x in witness)
        start = next(
            i for i, line in enumerate(source) if f"static int {method}(" in line
        )
        end = source.index("    }", start)
        markers = [
            (i + 1, source[i].strip())
            for i in range(start + 1, end)
            if "// Target" in source[i]
        ]
        first, second = query["target_lines"]
        assert markers == [
            (first, "a = 1; // Target 1"),
            (second, "b = 1; // Target 2"),
        ]
    return queries


@pytest.fixture(scope="module")
def endpoint_classes(ground_truth, prepared, tmp_path_factory):
    """Compile a separate validation copy that emits events at the marked lines."""
    lines = SOURCE.read_text().splitlines()
    for query in ground_truth.values():
        for target, line in enumerate(query["target_lines"], start=1):
            lines[line - 1] += f'\n            System.err.println("GROUP15:T{target}");'
    directory = tmp_path_factory.mktemp("pair-endpoint-observations")
    diagnostic_source = directory / SOURCE.name
    diagnostic_source.write_text("\n".join(lines) + "\n")
    subprocess.run(
        [
            "javac",
            "-g",
            "--release",
            "17",
            "-d",
            directory,
            diagnostic_source,
            ROOT / "group15/validation/PairRuntimeCheck.java",
        ],
        check=True,
        timeout=60,
    )
    return directory


# Each row samples every guard region used in its source-level impossibility proof.
NEGATIVE_REGIONS = {
    "p01": {-1: ("T1",), 0: (), 1: ("T2",)},
    "p03": {100002: ("T2",), 100003: ("T1",), 100004: ("T2",)},
    "p05": {-1: ("T1",), 0: ("T2",), 1: ("T2",)},
    "p07": {-1: ("T1",), 0: ("T2",), 1: ("T2",)},
}


def _replay(classes, method, arguments):
    return subprocess.run(
        [
            "java",
            "-Xint",
            "-cp",
            classes,
            "group15.validation.PairRuntimeCheck",
            method,
            *map(str, arguments),
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=5,
    )


@pytest.mark.parametrize("method", DESCRIPTORS)
def test_ground_truth_on_jvm(method, ground_truth, prepared, endpoint_classes):
    query = ground_truth[method]
    assert query["feasible"] == (method not in NEGATIVE_REGIONS)
    first, second = map(tuple, query["target_witnesses"])
    inputs = {first, second}
    if query["feasible"]:
        pair = tuple(query["pair_witness"])
        inputs.add(pair)
    else:
        inputs.update((x,) for x in NEGATIVE_REGIONS[method])

    observed = {}
    for arguments in inputs:
        original = _replay(prepared.classes, method, arguments)
        diagnostic = _replay(endpoint_classes, method, arguments)
        events = tuple(
            line.removeprefix("GROUP15:")
            for line in diagnostic.stderr.splitlines()
            if line.startswith("GROUP15:")
        )
        assert events in ((), ("T1",), ("T2",), ("T1", "T2"))
        assert original.stdout.strip() == diagnostic.stdout.strip() == str(len(events))
        observed[arguments] = events

    assert "T1" in observed[first]
    assert "T2" in observed[second]
    if query["feasible"]:
        assert observed[pair] == ("T1", "T2")
    else:
        assert all(len(events) < 2 for events in observed.values())
        for x, expected_events in NEGATIVE_REGIONS[method].items():
            assert observed[(x,)] == expected_events
