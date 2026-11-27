import json
import shutil
from collections import Counter
from dataclasses import replace
from itertools import product

import pytest

from group15 import evaluate_pairs as ev
from group15 import run_pair_experiments as single


@pytest.fixture(scope="module")
def suite(tmp_path_factory):
    if not all(shutil.which(tool) for tool in ("java", "javac", "javap")):
        pytest.skip("JDK 17+ required")
    return single.prepare_suite(tmp_path_factory.mktemp("paired-grid"))


def indexed(rows):
    return {
        (r["method_id"], r["strategy"], r["seed"], r["total_executions"]): {
            k: v for k, v in r.items() if k != "search_seconds"
        }
        for r in rows
    }


def raw_rows(output):
    return [
        json.loads(line) for line in (output / "trials.jsonl").read_text().splitlines()
    ]


def test_full_grid_has_balanced_order_and_shared_methods(suite, monkeypatch):
    seeds = tuple(range(20))
    budgets = (16, 64, 128, 256, 1024)
    strategies = ("A", "B", "C", "D")
    assert tuple(ev.SEEDS) == seeds and tuple(ev.BUDGETS) == budgets
    names = {method.method_id: name for name, method in suite.methods.items()}

    def record(
        method, strategy, *, seed, total_executions, constants=None, max_steps=None
    ):
        name = names[method.method_id]
        assert method is suite.methods[name]
        assert max_steps is None or max_steps == len(method.instructions)
        if strategy in ("B", "D"):
            assert constants == suite.benchmark.constants[name]
        else:
            assert constants is None
        return (method.method_id, strategy, seed, total_executions)

    monkeypatch.setattr(ev, "run_trial", record)
    trials = list(ev.run_grid(suite, ev.SEEDS, ev.BUDGETS))
    assert len(trials) == 3200
    assert set(trials) == set(product(names, strategies, seeds, budgets))
    positions = Counter()
    for start in range(0, len(trials), 4):
        block = trials[start : start + 4]
        method, _, seed, budget = block[0]
        offset = seed % 4
        assert [r[1] for r in block] == list(strategies[offset:] + strategies[:offset])
        for i, (method_id, strategy, s, cap) in enumerate(block):
            assert (method_id, s, cap) == (method, seed, budget)
            positions[method_id, budget, strategy, i] += 1
    assert set(positions.values()) == {5}


def test_grid_matches_single_seed_command(suite, capsys):
    assert single.main(["--seed", "15", "--total-executions", "256"]) == 0
    baseline = json.loads(capsys.readouterr().out)["results"]
    rows = json.loads(json.dumps(list(ev.run_grid(suite, (15,), (256,)))))
    assert len(rows) == len(baseline) == 32
    assert indexed(rows) == indexed(baseline)


def test_reordering_seeds_and_budgets_preserves_each_trial(suite):
    forward = ev.run_grid(suite, (1, 3), (16, 128))
    reverse = ev.run_grid(suite, (3, 1), (128, 16))
    assert indexed(forward) == indexed(reverse)


def test_scoring_distinguishes_verified_hits_misses_and_disagreements():
    feasible = "group15.PairReachability.p02:(I)I"
    infeasible = "group15.PairReachability.p01:(I)I"
    labels = {feasible: True, infeasible: False}
    rows = []
    replays = []
    for i, (method, witness, executions) in enumerate(
        (
            (feasible, (8,), 16),
            (feasible, None, 16),
            (infeasible, (3,), 3),
            (infeasible, None, 16),
        )
    ):
        rows.append(
            {
                "method_id": method,
                "strategy": "A",
                "seed": i % 2,
                "total_executions": 16,
                "verdict": "unknown" if witness is None else "reachable",
                "termination": "budget_exhausted" if witness is None else "ordered_hit",
                "witness": witness,
                "executions": executions,
                "fixed_executions": min(9, executions),
                "random_executions": max(0, executions - 9),
                "dictionary_executions": 0,
                "mutation_executions": 0,
                "cutoffs": 0,
                "covered_instructions": 2 * i + 2,
                "instruction_count": 10,
                "search_seconds": 2 * i + 1,
            }
        )
        if witness is not None:
            replays.append(
                {
                    "method_id": method,
                    "witness": witness,
                    "events": ["T1", "T2"],
                    "return_value": 2,
                }
            )
    summary = ev.summarise(rows, labels, replays)
    (group,) = summary["by_strategy_budget"]
    assert (group["trials"], group["feasible_trials"], group["discoveries"]) == (
        4,
        2,
        1,
    )
    assert group["discovery_rate"] == 0.5
    assert (
        group["unknown_feasible"],
        group["unknown_infeasible"],
        group["incorrect"],
    ) == (1, 1, 1)
    assert group["methods_discovered"] == [feasible]
    assert group["executions_to_witness"] == {"n": 1, "q1": 16, "median": 16, "q3": 16}
    assert group["search_seconds"] == {"n": 4, "q1": 2.5, "median": 4, "q3": 5.5}
    assert group["coverage_fraction"] == pytest.approx(
        {"n": 4, "q1": 0.35, "median": 0.5, "q3": 0.65}
    )
    assert (
        group["fixed_executions"],
        group["random_executions"],
        group["executions"],
    ) == (30, 21, 51)
    assert (
        group["cutoffs"]
        == group["mutation_executions"]
        == group["dictionary_executions"]
        == 0
    )
    negative = next(
        g for g in summary["by_method_strategy_budget"] if g["method_id"] == infeasible
    )
    assert negative["discovery_rate"] is None
    assert negative["executions_to_witness"] == {
        "n": 0,
        "q1": None,
        "median": None,
        "q3": None,
    }
    (disagreement,) = summary["disagreements"]
    assert disagreement["method_id"] == infeasible and tuple(
        disagreement["witness"]
    ) == (3,)
    with pytest.raises((RuntimeError, ValueError)):
        ev.summarise(rows, labels, replays[:1])
    with pytest.raises((RuntimeError, ValueError)):
        ev.summarise([dict(rows[1], verdict="unreachable")], labels, [])


def test_evaluation_writes_raw_metadata_and_replays_once(suite, tmp_path, monkeypatch):
    monkeypatch.setattr(ev, "BUILD", tmp_path)
    events = []

    def prepare(*args, **kwargs):
        events.append("prepare")
        return suite

    def trial(*args, **kwargs):
        events.append("trial")
        return single.run_trial(*args, **kwargs)

    def replay(prepared, rows):
        events.append("replay")
        assert prepared is suite and len(rows) == 64
        return single.replay_witnesses(prepared, rows)

    load = ev.load_labels

    def labels(prepared):
        events.append("labels")
        return load(prepared)

    monkeypatch.setattr(ev, "prepare_suite", prepare)
    monkeypatch.setattr(ev, "run_trial", trial)
    monkeypatch.setattr(ev, "replay_witnesses", replay)
    monkeypatch.setattr(ev, "load_labels", labels)
    output = tmp_path / "grid"
    ev.evaluate(output, seeds=(0, 1), budgets=(2,))
    summary = json.loads((output / "summary.json").read_text())
    rows = raw_rows(output)
    assert events[:65] == ["prepare"] + ["trial"] * 64
    assert sorted(events[65:]) == ["labels", "replay"]
    assert len(rows) == len(indexed(rows)) == 64
    assert summary["source_sha256"] == suite.benchmark.source_sha256
    assert all(
        summary["environment"][k]
        for k in ("python_version", "java_version", "platform")
    )
    assert summary["disagreements"] == []
    (replay,) = summary["replays"]
    hits = [r for r in rows if r["verdict"] == "reachable"]
    assert len(hits) == 8
    assert all(
        (r["method_id"], r["witness"]) == (replay["method_id"], replay["witness"])
        for r in hits
    )
    assert replay["events"] == ["T1", "T2"]
    groups = {g["strategy"]: g for g in summary["by_strategy_budget"]}
    for group in groups.values():
        assert group["discovery_rate"] == 2 / 8
        assert group["methods_discovered"] == [replay["method_id"]]
        assert group["executions"] == 32
    assert groups["B"]["executions_to_witness"] == groups["D"]["executions_to_witness"]


@pytest.mark.parametrize(
    "events,value",
    [(["T2", "T1"], 2), (["T1"], 2), (["T1", "T2"], 0), (["T1", "T2"], 2.0)],
)
def test_invalid_replay_cannot_verify_a_discovery(events, value):
    identity = {"method_id": "group15.PairReachability.p02:(I)I", "witness": [6]}
    row = dict(identity, strategy="B", total_executions=16, verdict="reachable")
    valid = dict(identity, events=["T1", "T2"], return_value=2)
    invalid = dict(identity, events=events, return_value=value)
    with pytest.raises(ValueError, match="Invalid JVM replay evidence"):
        ev.summarise([row], {row["method_id"]: True}, [valid, invalid])


def test_failed_verification_keeps_raw_and_removes_previous_summary(
    suite, tmp_path, monkeypatch
):
    monkeypatch.setattr(ev, "BUILD", tmp_path)
    monkeypatch.setattr(ev, "prepare_suite", lambda *args, **kwargs: suite)
    output = tmp_path / "grid"
    output.mkdir()
    (output / "summary.json").write_text('{"previous_success": true}')

    def reject(prepared, rows):
        assert len(raw_rows(output)) == len(rows) == 32
        raise RuntimeError("JVM rejected a witness")

    monkeypatch.setattr(ev, "replay_witnesses", reject)
    with pytest.raises(RuntimeError, match="JVM rejected"):
        ev.evaluate(output, seeds=(0,), budgets=(2,))
    assert len(raw_rows(output)) == 32
    assert not (output / "summary.json").exists()


def test_labels_match_the_prepared_benchmark(suite):
    labels = ev.load_labels(suite)
    assert set(labels) == {m.method_id for m in suite.methods.values()}
    assert sum(labels.values()) == 4
    with pytest.raises(ValueError):
        ev.load_labels(
            replace(suite, benchmark=replace(suite.benchmark, source_sha256="wrong"))
        )
    with pytest.raises(ValueError):
        ev.load_labels(replace(suite, methods={"p01": suite.methods["p01"]}))


def test_output_is_restricted_to_build(tmp_path, monkeypatch):
    monkeypatch.setattr(ev, "BUILD", tmp_path / "build")
    output = tmp_path / "outside"
    with pytest.raises(ValueError):
        ev.evaluate(output, seeds=(0,), budgets=(2,))
    assert not output.exists()
