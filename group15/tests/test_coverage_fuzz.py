import json
import random
import shutil
from itertools import islice, product

import pytest

from group15 import run_coverage_pairs as runner
from group15 import run_pairs
from group15.coverage_fuzz import fuzz, mutate_one
from group15.dictionary import FIXED_SEEDS, MAX_INT, MIN_INT
from group15.pair_execution import prepare_pair_methods, trace_candidate


@pytest.fixture(scope="module")
def methods(tmp_path_factory):
    if not all(shutil.which(tool) for tool in ("javac", "javap", "java")):
        pytest.skip("JDK 17+ required")
    build = tmp_path_factory.mktemp("coverage")
    prepared = run_pairs.compile_pair_benchmark(build, include_constants=False)
    assert prepared.constants == {}
    return prepare_pair_methods(prepared)


@pytest.fixture
def observed(monkeypatch):
    inputs = []

    def record(method, arguments, *, max_steps):
        inputs.append(arguments)
        return trace_candidate(method, arguments, max_steps=max_steps)

    monkeypatch.setattr(runner, "trace_candidate", record)
    return inputs


@pytest.mark.parametrize(
    "method,cap", [("p03", 0), ("p03", 8), ("p08", 10), ("p08", 81)]
)
def test_total_cap_limits_fixed_prefix(methods, observed, method, cap):
    case = methods[method]
    result = runner.run_c(case, seed=15, total_executions=cap)
    assert observed == list(islice(product(FIXED_SEEDS, repeat=case.arity), cap))
    assert result["executions"] == result["fixed_executions"] == cap
    assert result["mutation_executions"] == 0
    assert (result["verdict"], result["witness"]) == ("unknown", None)


def test_retention_and_duplicate_accounting():
    parents, attempts = [], []

    def observe(args):
        attempts.append(args)
        return frozenset({"entry", "branch"} if args == (1,) else {"entry"}), False

    def mutate(parent, rng):
        parents.append(parent)
        return (1,) if len(parents) == 1 else parent

    result = fuzz(
        [(0,), (2,)], observe, rng=random.Random(15), total_executions=32, mutate=mutate
    )
    assert attempts[:3] == [(0,), (2,), (1,)]
    assert set(parents) == {(0,), (1,)}
    assert attempts[3:] == parents[1:]
    assert result.executions == len(attempts) == 32
    assert (result.fixed_executions, result.mutation_executions) == (2, 30)
    assert (result.corpus_size, result.covered_instructions) == (2, 2)
    assert (result.verdict, result.witness) == ("unknown", None)


def test_empty_coverage_leaves_no_mutation_parents():
    result = fuzz(
        [(0,), (1,)],
        lambda args: (frozenset(), False),
        rng=random.Random(15),
        total_executions=20,
    )
    assert (result.verdict, result.witness) == ("unknown", None)
    assert result.fixed_executions == result.executions == 2
    assert (
        result.mutation_executions
        == result.corpus_size
        == result.covered_instructions
        == 0
    )


def test_observer_errors_propagate():
    def broken(args):
        raise ValueError("invalid target")

    with pytest.raises(ValueError, match="invalid target"):
        fuzz([(0,)], broken, rng=random.Random(0), total_executions=1)


@pytest.mark.parametrize(
    "options", [{"seed": None}, {"total_executions": -1}, {"max_steps": -1}]
)
def test_run_c_rejects_invalid_parameters(methods, observed, options):
    with pytest.raises(ValueError):
        runner.run_c(methods["p03"], **({"seed": 15, "total_executions": 0} | options))
    assert not observed


def test_mutation_preserves_signed_int32_and_changes_one_argument():
    parent = (MIN_INT, MAX_INT)
    rng = random.Random(15)
    changes = set()
    for _ in range(512):
        child = mutate_one(parent, rng)
        assert isinstance(child, tuple) and len(child) == len(parent)
        [(before, after)] = [(a, b) for a, b in zip(parent, child) if a != b]
        assert MIN_INT <= after <= MAX_INT
        bits_flipped = ((before ^ after) & 0xFFFFFFFF).bit_count()
        assert (after - before) % (1 << 32) in (1, 0xFFFFFFFF) or bits_flipped == 1
        changes.add((before, after))
    assert {(MIN_INT, MAX_INT), (MAX_INT, MIN_INT)} <= changes
    assert any(1 < abs(before - after) < 1 << 31 for before, after in changes)


def test_reproducibility_is_per_method(methods, observed):
    def sequences(names, seed):
        results = {}
        for name in names:
            observed.clear()
            result = runner.run_c(methods[name], seed=seed, total_executions=40)
            assert result["mutation_executions"] == 31
            results[name] = (
                observed.copy(),
                result["covered_instructions"],
                result["corpus_size"],
            )
        return results

    state = random.getstate()
    forward = sequences(("p01", "p03"), 15)
    assert sequences(("p03", "p01"), 15) == forward
    assert sequences(("p01", "p03"), 16) != forward
    assert random.getstate() == state


def test_pair_hit_can_add_no_coverage(methods):
    method = methods["p02"]
    traces = []

    def observe(args):
        trace = trace_candidate(method, args, max_steps=len(method.instructions))
        traces.append(trace)
        return trace.coverage, trace.pair_hit

    result = fuzz(
        [(0,), (10,), (6,), (8,)], observe, rng=random.Random(15), total_executions=10
    )
    assert [t.pair_hit for t in traces] == [False, False, True]
    assert traces[2].coverage == traces[0].coverage | traces[1].coverage
    assert (result.verdict, result.witness) == ("reachable", (6,))
    assert result.executions == 3 and result.corpus_size == 2


def test_p03_separate_invocations_cannot_satisfy_the_pair(methods):
    method = methods["p03"]

    def observe(args):
        trace = trace_candidate(method, args, max_steps=len(method.instructions))
        return trace.coverage, trace.pair_hit

    result = fuzz([(100003,), (0,)], observe, rng=random.Random(15), total_executions=2)
    assert result.covered_instructions == len(method.instructions)
    assert (result.verdict, result.witness) == ("unknown", None)


def test_p06_budget_and_step_boundaries(methods):
    method = methods["p06"]
    short = runner.run_c(method, seed=15, total_executions=1)
    full = runner.run_c(method, seed=15, total_executions=2)
    assert (short["verdict"], short["witness"], short["executions"]) == (
        "unknown",
        None,
        1,
    )
    assert (full["verdict"], full["witness"], full["executions"]) == (
        "reachable",
        (0, 1),
        2,
    )
    assert full["cutoffs"] == 0

    trace = trace_candidate(method, (0, 1), max_steps=len(method.instructions))
    before_second = trace.pcs.index(method.target_pcs[1])
    miss = runner.run_c(method, seed=15, total_executions=2, max_steps=before_second)
    hit = runner.run_c(method, seed=15, total_executions=2, max_steps=before_second + 1)
    assert miss["verdict"] == "unknown"
    assert (hit["verdict"], hit["witness"]) == ("reachable", (0, 1))
    assert hit["executions"] == 2 and hit["cutoffs"] >= 1


def test_c_cli_skips_dictionary_extraction(methods, monkeypatch, capsys):
    def forbidden(*args):
        pytest.fail("C extracted dictionary constants")

    monkeypatch.setattr(run_pairs, "extract_javap_constants", forbidden)
    assert runner.main(["--seed", "15", "--total-executions", "2"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["preparation_seconds"] >= 0
    assert {r["method_id"] for r in report["results"]} == {
        m.method_id for m in methods.values()
    }
    for row in report["results"]:
        assert row["strategy"] == "C" and row["execution_seconds"] >= 0
        assert (
            row["executions"]
            == row["fixed_executions"] + row["mutation_executions"]
            <= 2
        )
