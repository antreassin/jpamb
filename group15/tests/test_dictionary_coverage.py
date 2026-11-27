import json
import random
import shutil
from itertools import chain, islice, product

import pytest

from group15 import run_coverage_pairs as runner
from group15 import run_pairs
from group15.coverage_fuzz import mutate_one
from group15.dictionary import FIXED_SEEDS, dictionary_inputs
from group15.pair_execution import (
    PairMethod,
    PairTrace,
    prepare_pair_methods,
    trace_candidate,
)


@pytest.fixture(scope="module")
def benchmark(tmp_path_factory):
    if not all(shutil.which(tool) for tool in ("javac", "javap", "java")):
        pytest.skip("JDK 17+ required")
    prepared = run_pairs.compile_pair_benchmark(
        tmp_path_factory.mktemp("dictionary-coverage")
    )
    return prepared, prepare_pair_methods(prepared)


@pytest.fixture
def observed(monkeypatch):
    calls = []

    def record(method, args, *, max_steps):
        trace = trace_candidate(method, args, max_steps=max_steps)
        calls.append((args, trace))
        return trace

    monkeypatch.setattr(runner, "trace_candidate", record)
    return calls


def counts(row):
    return (
        row["fixed_executions"],
        row["dictionary_executions"],
        row["mutation_executions"],
    )


@pytest.mark.parametrize(
    "name,cap,phases,witness",
    [
        ("p03", 0, (0, 0, 0), None),
        ("p03", 8, (8, 0, 0), None),
        ("p03", 10, (9, 1, 0), None),
        ("p03", 12, (9, 3, 0), None),
        ("p03", 13, (9, 3, 1), None),
        ("p04", 10, (9, 1, 0), None),
        ("p04", 11, (9, 2, 0), (100003,)),
        ("p08", 130, (81, 49, 0), None),
        ("p08", 131, (81, 50, 0), (100003, 100003)),
    ],
)
def test_execution_boundaries(benchmark, observed, name, cap, phases, witness):
    prepared, methods = benchmark
    method = methods[name]
    constants = prepared.constants[name]
    row = runner.run_d(method, constants=constants, seed=15, total_executions=cap)
    assert row["executions"] == len(observed) == sum(phases)
    assert counts(row) == phases
    assert row["verdict"] == ("reachable" if witness else "unknown")
    assert row["witness"] == witness
    prefix = chain(
        product(FIXED_SEEDS, repeat=method.arity),
        dictionary_inputs(method.arity, constants, max_trials=cap),
    )
    seed_count = phases[0] + phases[1]
    assert [args for args, _ in observed[:seed_count]] == list(
        islice(prefix, seed_count)
    )


def test_dictionary_hit_without_new_coverage(benchmark, observed):
    prepared, methods = benchmark
    row = runner.run_d(
        methods["p02"],
        constants=prepared.constants["p02"],
        seed=15,
        total_executions=32,
    )
    assert (row["verdict"], row["witness"], counts(row)) == (
        "reachable",
        (6,),
        (9, 3, 0),
    )
    assert len(observed) == row["executions"] == 12
    prior = set().union(*(trace.coverage for _, trace in observed[:-1]))
    _, hit = observed[-1]
    assert hit.pair_hit and hit.coverage <= prior


@pytest.mark.parametrize("retain_fixed", [False, True])
def test_mutations_use_only_coverage_adding_parents(monkeypatch, retain_fixed):
    method = PairMethod(
        "synthetic", 1, ((0, "iconst_0", ""), (1, "ireturn", "")), (1, 0)
    )
    calls = []
    parent = (49,)

    def observe(method, args, *, max_steps):
        calls.append(args)
        pcs = (0,) if retain_fixed else ()
        if args in (parent, (50,), (51,)):
            pcs += (1,)
        return PairTrace(pcs, "returned", 0, method.method_id, False)

    monkeypatch.setattr(runner, "trace_candidate", observe)
    row = runner.run_d(method, constants=(50,), seed=15, total_executions=76)
    prefix = [(value,) for value in FIXED_SEEDS] + [parent, (50,), (51,)]
    rng = random.Random(15)
    retained = [(0,), parent] if retain_fixed else [parent]
    mutations = [mutate_one(rng.choice(retained), rng) for _ in range(64)]
    assert calls == prefix + mutations
    assert len(set(mutations)) < len(mutations)
    assert row["executions"] == len(calls) == 76
    assert counts(row) == (9, 3, 64)
    assert row["corpus_size"] == row["covered_instructions"] == len(retained)
    assert (row["verdict"], row["witness"]) == ("unknown", None)


def test_total_budget_can_fund_more_than_1000_dictionary_candidates():
    method = PairMethod("synthetic", 2, (), (0, 1))
    row = runner.run_d(
        method,
        constants=tuple(range(20, 70)),
        seed=15,
        total_executions=1084,
        max_steps=0,
    )
    assert counts(row) == (81, 1003, 0)
    assert row["executions"] == row["cutoffs"] == 1084
    assert row["corpus_size"] == 0


def test_reproducibility_and_empty_dictionary_match_c(benchmark, observed):
    prepared, methods = benchmark

    def sequence(name):
        observed.clear()
        runner.run_d(
            methods[name],
            constants=prepared.constants[name],
            seed=15,
            total_executions=32,
        )
        return [args for args, _ in observed]

    forward = {name: sequence(name) for name in ("p01", "p03")}
    assert {name: sequence(name) for name in ("p03", "p01")} == forward
    observed.clear()
    runner.run_c(methods["p01"], seed=15, total_executions=32)
    assert [args for args, _ in observed] == forward["p01"]


def test_d_cli_uses_local_constants_and_replays_witnesses(benchmark, observed, capsys):
    prepared, methods = benchmark
    assert (
        runner.main(["--strategy", "D", "--seed", "15", "--total-executions", "131"])
        == 0
    )
    rows = json.loads(capsys.readouterr().out)["results"]
    by_id = {row["method_id"]: row for row in rows}
    assert set(by_id) == {method.method_id for method in methods.values()}
    found = set()
    for name, method in methods.items():
        row = by_id[method.method_id]
        calls = [
            args for args, trace in observed if trace.method_id == method.method_id
        ]
        fixed, dictionary, mutations = counts(row)
        assert row["strategy"] == "D"
        assert row["executions"] == len(calls) == fixed + dictionary + mutations <= 131
        expected = dictionary_inputs(
            method.arity, prepared.constants[name], max_trials=dictionary
        )
        assert calls[fixed : fixed + dictionary] == list(expected)
        if row["verdict"] == "reachable":
            witness = tuple(row["witness"])
            assert trace_candidate(method, witness, max_steps=row["max_steps"]).pair_hit
            assert run_pairs.execute_candidate(prepared.classes, name, witness)
            found.add(name)
    assert found == {"p02", "p04", "p06", "p08"}
