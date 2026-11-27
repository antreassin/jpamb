import hashlib
import shutil
import subprocess
from collections import Counter
from dataclasses import replace
from pathlib import Path

import pytest

from group15 import category_backend as backend
from group15 import run_category_pairs as runner
from group15.run_pair_experiments import run_trial


@pytest.fixture(scope="module")
def dependencies():
    if not backend.DEFAULT_DEPS.is_dir():
        pytest.skip(
            "Supply the pinned Simone sources to run the category integration tests"
        )
    if not all(shutil.which(tool) for tool in ("java", "javac", "javap")):
        pytest.skip("JDK 17+ required")
    return backend.DEFAULT_DEPS


@pytest.fixture(scope="module")
def suite(dependencies, tmp_path_factory):
    return backend.prepare_categories(
        dependencies, tmp_path_factory.mktemp("categories")
    )


def test_pilot_releases_closed_lock_after_failure_and_success(tmp_path, monkeypatch):
    lock = tmp_path / ".running"
    handles = []
    original_open = Path.open

    def record_open(path, *args, **kwargs):
        handle = original_open(path, *args, **kwargs)
        if path == lock:
            handles.append(handle)
        return handle

    def pilot(_args):
        assert lock.is_file() and handles[-1].closed
        if len(handles) == 1:
            raise RuntimeError("pilot failed")
        return 0

    monkeypatch.setattr(runner, "OUTPUT", tmp_path)
    monkeypatch.setattr(Path, "open", record_open)
    monkeypatch.setattr(runner, "_pilot", pilot)
    assert runner.main([]) == 1
    assert not lock.exists()
    assert runner.main([]) == 0
    assert not lock.exists()


def test_modified_dependencies_rejected_before_execution(tmp_path):
    deps = tmp_path / "deps"
    for name in (
        "group15/validate.py",
        "group15/pair_dataset.py",
        "group15/src/group15/LineReachabilityCategories.java",
        "group15/validation/RuntimeCheck.java",
    ):
        path = deps / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("raise AssertionError('executed unverified dependency')\n")
    with pytest.raises((ValueError, RuntimeError)):
        backend.prepare_categories(deps, tmp_path / "build")


def test_support_inventory_and_target_mappings(suite):
    assert (
        suite.fingerprints["source_sha256"]
        == hashlib.sha256(suite.source.read_bytes()).hexdigest()
    )
    compiled = suite.classes / "group15/LineReachabilityCategories.class"
    assert (
        suite.fingerprints["class_sha256"]
        == hashlib.sha256(compiled.read_bytes()).hexdigest()
    )
    groups = {
        "branch": set(range(1, 16)) - {2},
        "arith": set(range(1, 21)) - {4},
        "loops": set(range(1, 21)) - {19},
        "methods": set(),
        "arrstr": set(),
        "objs": set(),
        "edge": {1, 3, 4, 9, 17, 18, 20},
    }
    expected = {f"{prefix}_{i:02}" for prefix, ids in groups.items() for i in ids}
    ids = {q["id"] for q in suite.queries}
    assert len(ids) == len(suite.queries) == 140
    assert set(suite.methods) == expected
    assert set(suite.unsupported) == ids - expected
    assert len(suite.methods) == 59 and len(suite.unsupported) == 81
    assert all(suite.unsupported.values())
    assert Counter(q["category"] for q in suite.queries) == dict.fromkeys(groups, 20)
    for query in suite.queries:
        assert {"feasible", "verdict", "label", "example", "witness"}.isdisjoint(query)
        assert len(query["targets"]) == 2
        if query["id"] in expected:
            method = suite.methods[query["id"]]
            assert all(t["method"] == query["method"] for t in query["targets"])
            assert [[pc] for pc in method.target_pcs] == [
                target["instruction_indices"] for target in query["targets"]
            ]


def test_actual_fetches_and_isolated_target_events(suite):
    method = suite.methods["branch_14"]
    assert suite.trace(method, (0,), max_steps=0).pcs == ()
    assert suite.trace(method, (0,), max_steps=1).pcs == (0,)
    t1, t2 = method.target_pcs
    for x, expected in ((1, {t1}), (3, {t2}), (0, set())):
        trace = suite.trace(method, (x,), max_steps=100)
        assert trace.status == "returned"
        assert trace.coverage == frozenset(trace.pcs)
        assert {t1, t2} & trace.coverage == expected
        assert len(trace.coverage) < len(method.instructions)
        assert not trace.pair_hit


def test_loop_repeated_pcs_and_cutoff_on_target(suite):
    method = suite.methods["loops_01"]
    trace = suite.trace(method, (4,), max_steps=1000)
    assert trace.status == "returned" and trace.pair_hit
    assert len(trace.pcs) > len(trace.coverage)
    t1, t2 = method.target_pcs
    before = trace.pcs.index(t2)
    assert trace.pcs.index(t1) < before
    for limit in (before, before + 1):
        bounded = suite.trace(method, (4,), max_steps=limit)
        assert bounded.status == "step_limit"
        assert bounded.pcs == trace.pcs[:limit]
        assert bounded.pair_hit == (limit > before)
    limited = suite.trace(method, (2**31 - 1,), max_steps=100)
    assert limited.status == "step_limit" and not limited.pair_hit


def test_reversed_targets_and_exceptional_termination(suite):
    opcodes = (
        "iconst_1",
        "istore_1",
        "iconst_1",
        "istore_2",
        "iconst_1",
        "iconst_0",
        "idiv",
        "ireturn",
    )
    method = replace(
        suite.methods["branch_01"],
        instructions=tuple((pc, op, "") for pc, op in enumerate(opcodes)),
        target_pcs=(2, 0),
    )
    trace = suite.trace(method, (0,), max_steps=10)
    assert trace.pcs == tuple(range(7)) and trace.status == "exception"
    assert trace.return_value is None and not trace.pair_hit
    ordered = suite.trace(replace(method, target_pcs=(0, 2)), (0,), max_steps=10)
    assert ordered.status == "exception" and ordered.pair_hit
    for strategy in ("A", "B", "C", "D"):
        row = run_trial(
            method,
            strategy,
            trace=suite.trace,
            seed=15,
            total_executions=1,
            max_steps=10,
            constants=(),
        )
        assert row["verdict"] == "unknown" and row["exceptional_executions"] == 1
        assert row["normal_returns"] == row["cutoffs"] == 0


def test_integer_results_against_original_jvm(suite):
    cases = [
        ("branch_14", (3,)),
        ("branch_15", (5,)),
        ("branch_15", (0,)),
        ("arith_08", (-4, -1)),
        ("arith_08", (4, -1)),
        ("edge_01", (46341,)),
        ("edge_03", (255,)),
        ("edge_04", (-65471,)),
        ("edge_09", (33,)),
        ("edge_17", (65535,)),
        ("edge_18", (-1,)),
    ]
    requests = [" ".join([name, *map(str, args)]) for name, args in cases]
    jvm = subprocess.run(
        [
            "java",
            "-Xint",
            "-cp",
            str(suite.classes),
            "group15.validation.RuntimeCheck",
            "group15.LineReachabilityCategories",
        ],
        input="\n".join(requests) + "\n",
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    returns = [int(line) for line in jvm.stdout.splitlines()]
    assert len(returns) == len(cases)
    for (name, args), returned in zip(cases, returns, strict=True):
        trace = suite.trace(suite.methods[name], args, max_steps=1000)
        assert trace.status == "returned" and trace.return_value == returned
        assert trace.pair_hit == (returned == 2)


def test_c_can_run_without_extraction_or_labels(dependencies, tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("C requested dictionary constants or labels")

    monkeypatch.setattr(backend, "extract_javap_constants", forbidden)
    monkeypatch.setattr(runner, "load_labels", forbidden)
    prepared = backend.prepare_categories(
        dependencies, tmp_path, include_constants=False
    )
    rows = runner.run_searches(
        prepared, ("C",), seed=15, total_executions=1, max_steps=50
    )
    assert len(rows) == 140
    assert all(row["executions"] == int(row["id"] in prepared.methods) for row in rows)


def test_matched_searches_and_distinct_jvm_replay(suite, tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Search tried to load ground truth")

    config = {"seed": 15, "total_executions": 3, "max_steps": 100}
    with monkeypatch.context() as guard:
        guard.setattr(runner, "load_labels", forbidden)
        first = runner.run_searches(suite, ("A", "B", "C", "D"), **config)
        second = runner.run_searches(suite, ("D", "C", "B", "A"), **config)

    def indexed(rows):
        return {
            (r["id"], r["strategy"]): {
                k: v for k, v in r.items() if k != "search_seconds"
            }
            for r in rows
        }

    assert len(first) == len(indexed(first)) == 560
    assert indexed(first) == indexed(second)
    for row in first:
        if row["id"] in suite.unsupported:
            assert row["verdict"] == "unsupported" and row["executions"] == 0
        else:
            assert row["verdict"] in ("reachable", "unknown")
            assert row["executions"] <= 3
            assert (
                row["normal_returns"] + row["cutoffs"] + row["exceptional_executions"]
                == row["executions"]
            )

    hits = [r for r in first if r["id"] == "branch_15"]
    assert all(
        r["verdict"] == "reachable" and tuple(r["witness"]) == (0,) for r in hits
    )
    replays = runner.replay_witnesses(suite, hits, tmp_path)
    (replay,) = replays
    assert replay["method_id"] == hits[0]["method_id"]
    assert replay["events"] == ["T1", "T2"] and replay["return_value"] == 2
    labels = runner.load_labels(suite.source)
    summary = runner.score(hits, labels, replays)
    assert all(g["reachable"] == 1 for g in summary["categories"])
    assert not summary["disagreements"]
    conflict = runner.score(hits, {**labels, "branch_15": False}, replays)
    assert conflict["disagreements"]
    assert all(g["disagreements"] == 1 for g in conflict["categories"])
    with pytest.raises((RuntimeError, ValueError)):
        runner.score(hits, labels, [])
