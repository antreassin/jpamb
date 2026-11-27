"""Execution budgets and paired search behavior shared by A and B"""

import random
import shutil
from itertools import islice, product

import pytest

from group15 import compare_pairs as cmp
from group15 import run_pairs
from group15.dictionary import FIXED_SEEDS, MAX_INT, MIN_INT


@pytest.fixture
def prepared(tmp_path):
    return run_pairs.PreparedBenchmark(
        tmp_path, {"p04": (0, 1, 100003), "p08": (0, 1, 100003)}, 0.5
    )


def record_run(monkeypatch, prepared, strategy, method, cap, *, seed=15, hit=None):
    seen = []

    def observe(classes, name, arguments):
        assert (classes, name) == (prepared.classes, method)
        seen.append(arguments)
        assert len(seen) <= cap, "The runner issued an invocation beyond the cap"
        return arguments == hit

    monkeypatch.setattr(run_pairs, "execute_candidate", observe)
    row = cmp.run_arm(prepared, method, strategy, seed=seed, total_executions=cap)
    counts = (row["fixed_trials"], row["dictionary_trials"], row["random_trials"])
    assert sum(counts) == row["executions"] == len(seen)
    assert (row["method"], row["strategy"], row["seed"]) == (method, strategy, seed)
    assert row["total_executions"] == cap
    assert row["oracle"] == run_pairs.ORACLE
    assert row["execution_seconds"] >= 0
    return row, seen


@pytest.mark.parametrize("strategy", ["A", "B"])
@pytest.mark.parametrize(
    "method,arity,cap",
    [("p04", 1, 0), ("p04", 1, 8), ("p04", 1, 9), ("p08", 2, 2), ("p08", 2, 81)],
)
def test_only_budgeted_fixed_tuples_reach_observer(
    monkeypatch, prepared, strategy, method, arity, cap
):
    row, seen = record_run(monkeypatch, prepared, strategy, method, cap)
    assert seen == list(islice(product(FIXED_SEEDS, repeat=arity), cap))
    assert row["fixed_trials"] == cap
    assert (row["verdict"], row["witness"]) == ("unknown", None)


@pytest.mark.parametrize(
    "arity,cap,field",
    [
        (3, 1, "arity"),
        (True, 1, "arity"),
        (1.0, 0, "arity"),
        (1, -1, "cap"),
        (1, True, "cap"),
        (1, 2.5, "cap"),
    ],
)
def test_invalid_search_parameters_rejected_before_observation(arity, cap, field):
    def observe(arguments):
        pytest.fail(f"Unexpected observer call with {arguments}")

    with pytest.raises(ValueError, match=field):
        cmp.budgeted_search(arity, (), observe, random.Random(15), cap)


@pytest.mark.parametrize(
    "method,cap,hit,expected,fixed,dictionary",
    [
        ("p04", 10, (100003,), None, 9, 1),
        ("p04", 11, (100003,), (100003,), 9, 2),
        ("p08", 130, (100003, 100003), None, 81, 49),
        ("p08", 131, (100003, 100003), (100003, 100003), 81, 50),
    ],
)
def test_b_discovery_boundaries(
    monkeypatch, prepared, method, cap, hit, expected, fixed, dictionary
):
    row, seen = record_run(monkeypatch, prepared, "B", method, cap, hit=hit)
    assert row["witness"] == expected
    assert row["verdict"] == ("unknown" if expected is None else "reachable")
    assert len(seen) == cap
    assert (row["fixed_trials"], row["dictionary_trials"]) == (fixed, dictionary)


def test_seeded_random_prefix_and_order_independence(monkeypatch, prepared):
    def sequences(order, seed):
        result = {}
        for strategy in order:
            row, seen = record_run(
                monkeypatch, prepared, strategy, "p04", 18, seed=seed
            )
            dictionary = 0 if strategy == "A" else 3
            assert row["dictionary_trials"] == dictionary
            assert row["random_trials"] == 18 - 9 - dictionary
            assert row["verdict"] == "unknown"
            result[strategy] = seen[9 + dictionary :]
        return result

    forward = sequences(("A", "B"), 15)
    assert sequences(("B", "A"), 15) == forward
    rng = random.Random(15)
    expected = [(rng.randint(MIN_INT, MAX_INT),) for _ in range(9)]
    assert forward == {"A": expected, "B": expected[:6]}
    assert sequences(("A", "B"), 16) != forward


@pytest.mark.parametrize("strategy,random_trials", [("A", 6), ("B", 3)])
def test_duplicate_invocations_consume_budget(
    monkeypatch, prepared, strategy, random_trials
):
    monkeypatch.setattr(random.Random, "randint", lambda self, lower, upper: 0)
    if strategy == "A":
        # Absence makes any attempted lookup of p04's bytecode constants fail.
        prepared = run_pairs.PreparedBenchmark(prepared.classes, {}, 0.5)
    row, seen = record_run(monkeypatch, prepared, strategy, "p04", 15)
    assert seen.count((0,)) == 1 + random_trials
    assert row["random_trials"] == random_trials
    assert (row["executions"], row["verdict"], row["witness"]) == (15, "unknown", None)


@pytest.mark.parametrize("strategy", ["A", "B"])
def test_jvm_failures_propagate(monkeypatch, prepared, strategy):
    def broken(*args):
        raise RuntimeError("JVM failed")

    monkeypatch.setattr(run_pairs, "execute_candidate", broken)
    with pytest.raises(RuntimeError, match="JVM failed"):
        cmp.run_arm(prepared, "p04", strategy, seed=15, total_executions=1)


def test_same_compiled_methods_and_oracle_on_jvm(tmp_path):
    if not all(shutil.which(tool) for tool in ("javac", "javap", "java")):
        pytest.skip("JDK 17+ required")
    compiled = run_pairs.compile_pair_benchmark(tmp_path)
    for strategy in ("A", "B"):
        row = cmp.run_arm(compiled, "p06", strategy, seed=15, total_executions=12)
        assert (row["verdict"], row["witness"], row["executions"]) == (
            "reachable",
            (0, 1),
            2,
        )
        assert row["fixed_trials"] == 2
    for cap, witness in [(10, None), (11, (100003,))]:
        row = cmp.run_arm(compiled, "p04", "B", seed=15, total_executions=cap)
        assert row["witness"] == witness
        assert row["executions"] == cap
