import json
import random
import shutil
from collections import Counter
from itertools import product

import pytest

from group15 import compare_pairs, run_coverage_pairs, run_pairs
from group15 import run_pair_experiments as exp
from group15.dictionary import FIXED_SEEDS, extract_javap_constants
from group15.pair_execution import trace_candidate

STRATEGIES = ("A", "B", "C", "D")
PHASES = (
    "fixed_executions",
    "dictionary_executions",
    "random_executions",
    "mutation_executions",
)
pytestmark = pytest.mark.skipif(
    not all(shutil.which(tool) for tool in ("javac", "javap", "java")),
    reason="JDK 17+ required",
)


@pytest.fixture(scope="module")
def suite(tmp_path_factory):
    return exp.prepare_suite(tmp_path_factory.mktemp("pair-experiments"), STRATEGIES)


@pytest.fixture
def observed(monkeypatch):
    calls = []

    def record(method, args, *, max_steps):
        trace = trace_candidate(method, args, max_steps=max_steps)
        calls.append((method, args, max_steps, trace))
        return trace

    monkeypatch.setattr(exp, "trace_candidate", record)
    monkeypatch.setattr(run_coverage_pairs, "trace_candidate", record)
    return calls


def trial(suite, name, strategy, cap, *, max_steps=None):
    constants = suite.benchmark.constants[name] if strategy in ("B", "D") else None
    return exp.run_trial(
        suite.methods[name],
        strategy,
        constants=constants,
        seed=15,
        total_executions=cap,
        max_steps=max_steps,
    )


def test_constants_extracted_once_per_compiled_method(tmp_path, monkeypatch):
    inputs = []

    def extract(instructions):
        inputs.append(tuple(instructions))
        return extract_javap_constants(instructions)

    def unexpected(instructions):
        pytest.fail("Constants extracted during shared compilation")

    monkeypatch.setattr(run_pairs, "extract_javap_constants", unexpected)
    monkeypatch.setattr(exp, "extract_javap_constants", extract)
    prepared = exp.prepare_suite(tmp_path, ("B", "D"))
    assert Counter(inputs) == Counter(m.instructions for m in prepared.methods.values())
    assert prepared.benchmark.constants == {
        name: extract_javap_constants(m.instructions)
        for name, m in prepared.methods.items()
    }
    assert (
        prepared.preparation_seconds >= 0 and prepared.constant_extraction_seconds >= 0
    )


@pytest.mark.parametrize("strategy", STRATEGIES)
def test_real_calls_match_budget_and_coverage(suite, strategy, observed, monkeypatch):
    method = suite.methods["p03"]
    monkeypatch.setattr(random.Random, "randint", lambda self, lo, hi: 0)
    for cap in (0, 5, 40):
        observed.clear()
        row = trial(suite, "p03", strategy, cap)
        assert all(
            m is method and limit == len(method.instructions)
            for m, _, limit, _ in observed
        )
        args = [args for _, args, _, _ in observed]
        prefix = list(product(FIXED_SEEDS, repeat=method.arity))[:cap]
        assert args[: len(prefix)] == prefix
        if cap == 40:
            assert len(set(args)) < len(args)
        coverage = set().union(*(trace.coverage for _, _, _, trace in observed))
        assert row["covered_instructions"] == len(coverage)
        assert sum(row[k] for k in PHASES) == row["executions"] == len(observed) == cap
        assert row["fixed_executions"] == len(prefix)
        assert row["cutoffs"] == 0
        assert (row["verdict"], row["witness"], row["termination"]) == (
            "unknown",
            None,
            "budget_exhausted",
        )
        assert (row["corpus_size"] is None) == (strategy in ("A", "B"))
        assert row["search_seconds"] >= 0


@pytest.mark.parametrize("strategy", STRATEGIES)
def test_ordered_hit_boundary_and_empty_coverage(suite, strategy):
    method = suite.methods["p06"]
    full = trace_candidate(method, (0, 1), max_steps=len(method.instructions))
    before_t2 = full.pcs.index(method.target_pcs[1])
    for bound, cap, termination, witness in (
        (before_t2, 2, "budget_exhausted", None),
        (before_t2 + 1, 20, "ordered_hit", (0, 1)),
    ):
        row = trial(suite, "p06", strategy, cap, max_steps=bound)
        assert (row["executions"], row["max_steps"]) == (2, bound)
        assert (row["termination"], row["witness"]) == (termination, witness)
        assert row["cutoffs"] > 0

    row = trial(suite, "p01", strategy, 20, max_steps=0)
    expected = (
        (9, "empty_corpus") if strategy in ("C", "D") else (20, "budget_exhausted")
    )
    assert (row["executions"], row["termination"]) == expected
    assert row["cutoffs"] == row["executions"]
    assert (row["verdict"], row["covered_instructions"]) == ("unknown", 0)


def test_method_and_strategy_order_independence(suite, observed):
    def run(names, strategies):
        rows = {}
        for name in names:
            for strategy in strategies:
                observed.clear()
                row = trial(suite, name, strategy, 40)
                row.pop("search_seconds")
                rows[name, strategy] = row, [args for _, args, _, _ in observed]
        return rows

    state = random.getstate()
    forward = run(("p01", "p03"), STRATEGIES)
    assert run(("p03", "p01"), STRATEGIES[::-1]) == forward
    assert random.getstate() == state


@pytest.mark.parametrize("strategy", ("C", "D"))
def test_existing_coverage_search_parity(suite, strategy):
    for name, cap in (("p03", 30), ("p08", 131)):
        unified = trial(suite, name, strategy, cap)
        method = suite.methods[name]
        if strategy == "C":
            old = run_coverage_pairs.run_c(method, seed=15, total_executions=cap)
        else:
            old = run_coverage_pairs.run_d(
                method,
                constants=suite.benchmark.constants[name],
                seed=15,
                total_executions=cap,
            )
        for key in (
            "verdict",
            "witness",
            "executions",
            "covered_instructions",
            "corpus_size",
            "cutoffs",
        ):
            assert unified[key] == old[key]
        for phase in PHASES:
            assert unified[phase] == old.get(phase, 0)


def test_cli_ac_selection_avoids_extraction_and_replays_once(monkeypatch, capsys):
    def forbidden(instructions):
        pytest.fail("A/C requested program constants")

    monkeypatch.setattr(exp, "extract_javap_constants", forbidden)
    monkeypatch.setattr(run_pairs, "extract_javap_constants", forbidden)
    assert (
        exp.main(["--strategies", "A", "C", "--seed", "15", "--total-executions", "2"])
        == 0
    )
    report = json.loads(capsys.readouterr().out)
    rows = report["results"]
    assert len(rows) == 16 and {r["strategy"] for r in rows} == {"A", "C"}
    assert all(row.keys() == rows[0].keys() for row in rows)
    assert report["constant_extraction_seconds"] == 0
    assert report["preparation_seconds"] >= 0 and report["replay_seconds"] >= 0
    hits = [row for row in rows if row["verdict"] == "reachable"]
    assert len(hits) == 2
    (replay,) = report["replays"]
    for hit in hits:
        assert (hit["method_id"], hit["witness"]) == (
            replay["method_id"],
            replay["witness"],
        )
    assert replay["witness"] == [0, 1]
    assert replay["return_value"] == 2 and replay["events"] == ["T1", "T2"]


def test_replay_rejects_reversed_jvm_events(suite, monkeypatch):
    row = trial(suite, "p06", "A", 2)
    run = exp.validate.run

    def reversed_events(command):
        if command[0] == "java":
            return "T2\nT1\n2\n"
        return run(command)

    monkeypatch.setattr(exp.validate, "run", reversed_events)
    with pytest.raises(RuntimeError, match="JVM replay mismatch"):
        exp.replay_witnesses(suite, [row])


@pytest.mark.slow
@pytest.mark.parametrize("strategy", ("A", "B"))
@pytest.mark.parametrize("name", tuple(run_pairs.METHODS))
def test_seed15_cap256_ab_jvm_parity(suite, strategy, name):
    baseline = compare_pairs.run_arm(
        suite.benchmark, name, strategy, seed=15, total_executions=256
    )
    row = trial(suite, name, strategy, 256)
    for key in (
        "method_id",
        "strategy",
        "seed",
        "total_executions",
        "verdict",
        "witness",
        "executions",
    ):
        assert row[key] == baseline[key]
    for phase in ("fixed", "dictionary", "random"):
        assert row[f"{phase}_executions"] == baseline[f"{phase}_trials"]
    assert row["mutation_executions"] == row["cutoffs"] == 0
