"""Tests for S1's bytecode dictionary and bounded B input generation."""

import json
import random
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from group15.dictionary import (
    FIXED_SEEDS,
    MAX_INT,
    MIN_INT,
    dictionary_inputs,
    dictionary_values,
    extract_javap_constants,
    extract_jvm_constants,
    search,
)


def test_jvm_extraction_ignores_metadata_and_noninteger_values():
    instructions = [
        {"opr": "push", "offset": 901, "value": {"type": "integer", "value": -7}},
        {"opr": "push", "offset": 902, "value": {"type": "int", "value": 100003}},
        {"opr": "push", "value": {"type": "integer", "value": -7}},
        {"opr": "incr", "index": 903, "amount": -2},
        {"opr": "push", "value": None},
        {"opr": "push", "value": {"type": "long", "value": 904}},
        {"opr": "push", "value": {"type": "float", "value": 905.0}},
        {"opr": "push", "value": {"type": "string", "value": "906"}},
        {"opr": "load", "index": 907},
        {"opr": "ifz", "target": 908},
        {"opr": "return", "expected": 909, "witness": [910], "line": 911},
    ]
    assert extract_jvm_constants(instructions) == (-7, -2, 100003)


@pytest.mark.parametrize(
    "value", [True, False, 1.0, "1", None, MIN_INT - 1, MAX_INT + 1]
)
def test_jvm_extraction_rejects_invalid_integer_literals(value):
    with pytest.raises(ValueError):
        extract_jvm_constants(
            [{"opr": "push", "value": {"type": "integer", "value": value}}]
        )
    with pytest.raises(ValueError):
        extract_jvm_constants([{"opr": "incr", "index": 0, "amount": value}])


def test_jvm_extraction_rejects_missing_push_value():
    with pytest.raises(ValueError):
        extract_jvm_constants([{"opr": "push", "offset": 0}])


def test_javap_extraction_handles_integer_encodings_and_ignores_other_operands():
    instructions = [
        (900, "iconst_m1", ""),
        *[(901 + n, f"iconst_{n}", "") for n in range(6)],
        (910, "bipush", "-128"),
        (912, "sipush", "32767"),
        (915, "ldc", "#987 // int 100003"),
        (917, "ldc_w", f"#988 // int {MIN_INT}"),
        (920, "ldc_w", f"#989 // int {MAX_INT}"),
        (923, "iinc", "991, -7"),
        (926, "ldc", "#992 // String 123456"),
        (928, "ldc", "#993 // float 123.0f"),
        (930, "ldc2_w", "#994 // long 456l"),
        (933, "iload", "995"),
        (935, "if_icmpne", "996"),
        (938, "return", ""),
    ]
    assert extract_javap_constants(instructions) == (
        MIN_INT,
        -128,
        -7,
        -1,
        0,
        1,
        2,
        3,
        4,
        5,
        32767,
        100003,
        MAX_INT,
    )


def test_extraction_accepts_empty_instruction_lists():
    assert extract_jvm_constants([]) == ()
    assert extract_javap_constants([]) == ()


def test_tracked_jvm2json_artifact_uses_actual_project_format():
    artifact = ROOT / "target" / "decompiled" / "jpamb" / "cases" / "Simple.json"
    methods = json.loads(artifact.read_text())["methods"]
    method = next(
        method for method in methods if method["name"] == "checkBeforeDivideByN2"
    )
    assert extract_jvm_constants(method["code"]["bytecode"]) == (0, 1, 10)


@pytest.mark.parametrize(
    "opcode,operand",
    [
        ("bipush", "not-an-integer"),
        ("sipush", str(MAX_INT + 1)),
        ("ldc", "#123"),
        ("ldc", "#123 // int 1.5"),
        ("ldc_w", f"#123 // int {MIN_INT - 1}"),
        ("iinc", "0, missing"),
    ],
)
def test_javap_extraction_rejects_unresolved_or_invalid_integer_operands(
    opcode, operand
):
    with pytest.raises(ValueError):
        extract_javap_constants([(0, opcode, operand)])


def test_execution_failure_propagates_instead_of_becoming_unknown():
    def unsupported(arguments):
        raise NotImplementedError("unsupported execution")

    with pytest.raises(NotImplementedError, match="unsupported execution"):
        search(1, [], unsupported, random.Random(0))


def test_dictionary_values_preserve_baseline_seeds_and_add_sorted_neighbors():
    assert FIXED_SEEDS == (0, 1, -1, 2, -2, MIN_INT, MIN_INT + 1, MAX_INT - 1, MAX_INT)
    assert dictionary_values([100003, -7, 100003]) == FIXED_SEEDS + (
        -8,
        -7,
        -6,
        100002,
        100003,
        100004,
    )
    assert dictionary_values([]) == FIXED_SEEDS


def test_dictionary_neighbors_never_wrap_outside_java_int_range():
    values = dictionary_values([MIN_INT, MAX_INT])
    assert values == FIXED_SEEDS
    assert all(MIN_INT <= value <= MAX_INT for value in values)
    assert len(values) == len(set(values))


@pytest.mark.parametrize("value", [True, 1.0, "1", None, MIN_INT - 1, MAX_INT + 1])
def test_dictionary_pool_rejects_non_java_integer_constants(value):
    with pytest.raises(ValueError):
        dictionary_values([value])
    with pytest.raises(ValueError):
        list(dictionary_inputs(1, [value]))
    with pytest.raises(ValueError):
        search(1, [value], lambda _: True, random.Random(0))


def test_dictionary_inputs_include_mixed_and_equal_pairs_without_repeating_baseline():
    candidates = list(dictionary_inputs(2, [100], max_trials=1000))
    assert len(candidates) == 12**2 - len(FIXED_SEEDS) ** 2
    assert len(candidates) == len(set(candidates))
    assert (0, 100) in candidates
    assert (100, 0) in candidates
    assert (100, 100) in candidates
    assert (99, 101) in candidates
    assert not any(
        all(value in FIXED_SEEDS for value in candidate) for candidate in candidates
    )
    assert list(dictionary_inputs(1, [100], max_trials=2)) == [(99,), (100,)]
    assert list(dictionary_inputs(2, [], max_trials=1000)) == []
    assert list(dictionary_inputs(1, [100], max_trials=0)) == []


def test_dictionary_input_iteration_is_lazy_and_bounded():
    # A full Cartesian result would have millions of tuples. Consume only three.
    candidates = dictionary_inputs(2, range(10_000, 13_000), max_trials=3)
    assert iter(candidates) is candidates
    assert len(list(candidates)) == 3


@pytest.mark.parametrize("arity", [0, 3, -1, True, 1.0, "1"])
def test_unsupported_arity_is_rejected(arity):
    with pytest.raises(ValueError):
        list(dictionary_inputs(arity, [100]))
    with pytest.raises(ValueError):
        search(arity, [100], lambda _: True, random.Random(0))


@pytest.mark.parametrize("budget", [-1, True, 1.0, "1", None])
def test_invalid_trial_budgets_are_rejected_before_search(budget):
    with pytest.raises(ValueError):
        list(dictionary_inputs(1, [100], max_trials=budget))
    with pytest.raises(ValueError):
        search(1, [100], lambda _: True, random.Random(0), dictionary_trials=budget)
    with pytest.raises(ValueError):
        search(1, [100], lambda _: True, random.Random(0), random_trials=budget)


def test_fixed_phase_stops_on_first_witness_without_consuming_randomness():
    rng = random.Random(77)
    initial_state = rng.getstate()
    seen = []

    def hits(arguments):
        seen.append(arguments)
        return arguments == (1,)

    result = search(1, [100], hits, rng)
    assert result.verdict == "reachable"
    assert result.witness == (1,)
    assert (result.fixed_trials, result.dictionary_trials, result.random_trials) == (
        2,
        0,
        0,
    )
    assert seen == [(0,), (1,)]
    assert rng.getstate() == initial_state


def test_dictionary_phase_stops_on_witness_and_reports_actual_trials():
    rng = random.Random(77)
    initial_state = rng.getstate()
    seen = []

    def hits(arguments):
        seen.append(arguments)
        return arguments == (100,)

    result = search(1, [100], hits, rng)
    assert result.verdict == "reachable"
    assert result.witness == (100,)
    assert (result.fixed_trials, result.dictionary_trials, result.random_trials) == (
        9,
        2,
        0,
    )
    assert len(seen) == 11
    assert rng.getstate() == initial_state


def test_exhausted_budget_means_unknown_and_dictionary_budget_is_honored():
    result = search(
        1,
        [100],
        lambda arguments: arguments == (100,),
        random.Random(0),
        dictionary_trials=1,
        random_trials=0,
    )
    assert result.verdict == "unknown"
    assert result.witness is None
    assert (result.fixed_trials, result.dictionary_trials, result.random_trials) == (
        9,
        1,
        0,
    )


def test_random_phase_uses_inclusive_java_bounds_and_stops_on_witness():
    class BoundaryRandom(random.Random):
        def __init__(self):
            super().__init__(0)
            self.bounds = []

        def randint(self, lower, upper):
            self.bounds.append((lower, upper))
            return MIN_INT if len(self.bounds) % 2 else MAX_INT

    rng = BoundaryRandom()
    seen = []

    def hits(arguments):
        seen.append(arguments)
        return len(seen) > len(FIXED_SEEDS) ** 2

    result = search(2, [], hits, rng, dictionary_trials=0, random_trials=10)
    assert result.verdict == "reachable"
    assert result.witness == (MIN_INT, MAX_INT)
    assert (result.fixed_trials, result.dictionary_trials, result.random_trials) == (
        81,
        0,
        1,
    )
    assert rng.bounds == [(MIN_INT, MAX_INT), (MIN_INT, MAX_INT)]


def test_search_is_reproducible_with_caller_rng_and_does_not_change_global_rng():
    global_state = random.getstate()

    def run(seed):
        seen = []

        def misses(arguments):
            seen.append(arguments)
            return False

        result = search(
            2, [100], misses, random.Random(seed), dictionary_trials=4, random_trials=5
        )
        return result, seen

    first, seen = run(23)
    assert run(23) == (first, seen)
    assert run(24)[1] != seen
    assert first.verdict == "unknown"
    assert first.witness is None
    assert (first.fixed_trials, first.dictionary_trials, first.random_trials) == (
        81,
        4,
        5,
    )
    assert len(seen) == 90
    assert all(MIN_INT <= value <= MAX_INT for arguments in seen for value in arguments)
    assert random.getstate() == global_state


@pytest.mark.skipif(
    not all(shutil.which(tool) for tool in ("javac", "java", "javap")),
    reason="Real bytecode integration requires a JDK 17+ on PATH",
)
def test_compiled_group15_dictionary_search_and_jvm_witness_replay(tmp_path):
    from group15.validate import Parser, execute_bytecode, parse_disassembly

    source = ROOT / "group15" / "src" / "group15" / "LineReachability.java"
    harness = ROOT / "group15" / "validation" / "RuntimeCheck.java"
    classes = tmp_path / "classes"
    classes.mkdir()

    def run(command, **kwargs):
        completed = subprocess.run(
            command, text=True, capture_output=True, timeout=60, check=False, **kwargs
        )
        assert completed.returncode == 0, completed.stdout + completed.stderr
        return completed.stdout

    run(
        [
            "javac",
            "-g",
            "--release",
            "17",
            "-d",
            str(classes),
            str(source),
            str(harness),
        ]
    )
    disassembly = run(
        [
            "javap",
            "-classpath",
            str(classes),
            "-c",
            "-l",
            "-p",
            "-s",
            "group15.LineReachability",
        ]
    )
    methods = Parser(source.read_text()).parse()
    compiled = parse_disassembly(disassembly, methods)
    results = {}
    requests = []
    constants_by_method = {}
    for name, method in compiled.items():
        constants = extract_javap_constants(method["instructions"])
        constants_by_method[name] = constants
        # Only bytecode-derived constants enter B; labels and supplied witnesses
        # are not loaded until evaluation below.
        result = search(
            len(methods[name].params),
            constants,
            lambda arguments, method=method: execute_bytecode(method, arguments)[1],
            random.Random(15),
            dictionary_trials=1000,
            random_trials=0,
        )
        results[name] = result
        if result.witness is not None:
            requests.append(" ".join([name, *map(str, result.witness)]))

    # Includes executable bookkeeping and irrelevant noise, not just guard values.
    assert constants_by_method["q01"] == (-7, 0, 1)
    assert constants_by_method["q05"] == (0, 1, 100003)
    assert constants_by_method["q19"] == (-7, 0, 1)
    assert constants_by_method["q11"] == (0, 1, 100002, 100004)
    assert results["q11"].witness == (100003,)

    metadata = json.loads((ROOT / "group15" / "targets.json").read_text())
    for query in metadata["queries"]:
        result = results[query["method"]]
        assert result.verdict == (
            "reachable" if query["expected"] == "reachable" else "unknown"
        )
        assert result.random_trials == 0
    assert len(requests) == 15
    output = run(
        ["java", "-Xint", "-cp", str(classes), "group15.validation.RuntimeCheck"],
        input="\n".join(requests) + "\n",
    )
    assert output.splitlines() == ["1"] * 15
