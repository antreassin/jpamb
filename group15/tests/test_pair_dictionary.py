"""Dictionary B experiments and independent validation of the eight pair cases."""

import hashlib
import json
import shutil
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from group15 import run_pairs
from group15.dictionary import extract_javap_constants
from group15.pair_execution import prepare_pair_methods, trace_candidate
from group15.validate import trace_bytecode

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


@pytest.fixture(scope="module")
def pair_methods(prepared):
    return prepare_pair_methods(prepared)


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
def test_ground_truth_on_jvm(
    method, ground_truth, prepared, endpoint_classes, pair_methods
):
    query = ground_truth[method]
    pair_method = pair_methods[method]
    target_names = dict(zip(pair_method.target_pcs, ("T1", "T2")))
    compiled = prepared.methods[method]
    method_id = f"group15.PairReachability.{method}:{query['descriptor']}"
    bound = len(compiled.instructions)
    for line, pc in zip(query["target_lines"], pair_method.target_pcs, strict=True):
        assert (line, compiled.instructions[pc][0]) in compiled.lines
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
        trace = trace_candidate(pair_method, arguments, max_steps=bound)
        assert trace.method_id == method_id
        assert trace.status == "returned"
        assert trace.return_value == int(original.stdout)
        traced_events = tuple(target_names[pc] for pc in trace.pcs if pc in target_names)
        assert traced_events == events
        assert trace.pair_hit == (events == ("T1", "T2"))
        assert trace.coverage == frozenset(trace.pcs)
        observed[arguments] = events

    assert "T1" in observed[first]
    assert "T2" in observed[second]
    if query["feasible"]:
        assert observed[pair] == ("T1", "T2")
    else:
        assert all(len(events) < 2 for events in observed.values())
        for x, expected_events in NEGATIVE_REGIONS[method].items():
            assert observed[(x,)] == expected_events


def test_trace_step_boundaries(pair_methods):
    method = pair_methods["p04"]
    arguments = (100003,)
    full = trace_candidate(method, arguments, max_steps=len(method.instructions))
    assert full.pcs == tuple(range(len(method.instructions)))
    assert (full.status, full.return_value, full.pair_hit) == ("returned", 2, True)

    before_second = full.pcs.index(method.target_pcs[1])
    bounds = (0, before_second, before_second + 1, len(full.pcs) - 1, len(full.pcs))
    for bound in bounds:
        trace = trace_candidate(method, arguments, max_steps=bound)
        assert trace.pcs == full.pcs[:bound]
        assert trace.coverage == frozenset(full.pcs[:bound])
        assert trace.pair_hit == (bound > before_second)
        if bound == len(full.pcs):
            assert (trace.status, trace.return_value) == ("returned", 2)
        else:
            assert (trace.status, trace.return_value) == ("step_limit", None)


def test_trace_target_order_is_independent_of_return_value(pair_methods):
    method = pair_methods["p04"]
    reversed_targets = replace(method, target_pcs=method.target_pcs[::-1])
    trace = trace_candidate(
        reversed_targets, (100003,), max_steps=len(method.instructions)
    )
    assert set(method.target_pcs) <= trace.coverage
    assert trace.return_value == 2
    assert not trace.pair_hit


@pytest.mark.parametrize("name,first_input", [("p03", 100003), ("p05", -1)])
def test_trace_targets_are_local_to_one_invocation(pair_methods, name, first_input):
    method = pair_methods[name]
    first_pc, second_pc = method.target_pcs
    bound = len(method.instructions)
    only_first = trace_candidate(method, (first_input,), max_steps=bound)
    only_second = trace_candidate(method, (0,), max_steps=bound)
    targets = set(method.target_pcs)
    assert targets & only_first.coverage == {first_pc}
    assert targets & only_second.coverage == {second_pc}
    assert not only_first.pair_hit and not only_second.pair_hit
    if name == "p05":
        assert method.instructions[only_first.pcs[-1]][1] == "ireturn"
        assert only_first.pcs[-1] < second_pc


def test_trace_short_circuit_coverage(pair_methods):
    method = pair_methods["p08"]
    short = trace_candidate(method, (0, 1), max_steps=len(method.instructions))
    longer = trace_candidate(method, (100003, 1), max_steps=len(method.instructions))
    assert short.method_id == longer.method_id
    assert not short.pair_hit and not longer.pair_hit
    assert short.return_value == longer.return_value == 0
    assert longer.coverage > short.coverage


@pytest.mark.parametrize(
    "problem", ["missing", "ambiguous", "same_entry", "wrong_opcode"]
)
def test_trace_rejects_invalid_line_mapping(prepared, ground_truth, problem):
    method = prepared.methods["p04"]
    first, second = ground_truth["p04"]["target_lines"]
    offsets = dict(method.lines)
    lines = [(line, offset) for line, offset in method.lines if line != second]
    if problem == "ambiguous":
        lines.extend([(second, offsets[first]), (second, offsets[second])])
    elif problem == "same_entry":
        lines.append((second, offsets[first]))
    elif problem == "wrong_opcode":
        lines.append((second, method.instructions[1][0]))
    methods = {**prepared.methods, "p04": replace(method, lines=lines)}
    with pytest.raises(ValueError):
        prepare_pair_methods(replace(prepared, methods=methods))


def test_trace_rejects_stale_source(prepared):
    with pytest.raises(ValueError, match="source differs"):
        prepare_pair_methods(replace(prepared, source_sha256="stale"))


@pytest.mark.parametrize("bound", [-1, True, 1.5])
def test_trace_invalid_step_bound(pair_methods, bound):
    with pytest.raises(ValueError):
        trace_candidate(pair_methods["p04"], (0,), max_steps=bound)


@pytest.mark.parametrize("arguments", [(), (0, True), (2**31, 0)])
def test_trace_invalid_java_arguments(pair_methods, arguments):
    with pytest.raises(ValueError):
        trace_candidate(pair_methods["p08"], arguments, max_steps=0)


@pytest.mark.parametrize(
    "left,right,expected", [(2**31 - 1, 1, -(2**31)), (-(2**31), -1, 2**31 - 1)]
)
def test_trace_java_iadd_wraps(left, right, expected):
    instructions = [
        (0, "iload_0", ""), (1, "iload_1", ""), (2, "iadd", ""), (3, "ireturn", "")
    ]
    result = trace_bytecode(instructions, (left, right), max_steps=4)
    assert (result.status, result.return_value) == ("returned", expected)


@pytest.mark.parametrize("instruction", [(0, "goto", "0"), (0, "invokestatic", "#1")])
def test_trace_rejects_unsupported_execution(instruction):
    with pytest.raises(ValueError):
        trace_bytecode([instruction], (), max_steps=1)
