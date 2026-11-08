import copy
import json
import random
import subprocess
import sys

import pytest
import run_a
import validate
from basic_search import FIXED_SEEDS


def test_all_queries_record_positional_witness_and_actual_trial_counts(example_inputs):
    inputs, text = example_inputs
    results = run_a.analyse(inputs, text, seed=0)
    assert len(results) == 30
    for result in results:
        assert result["verdict"] == "reachable"
        assert result["witness"] == [0]
        assert result["witness_phase"] == "fixed"
        assert result["fixed_trials"] == 1
        assert result["random_trials"] == 0


def test_method_return_value_is_not_a_target_hit(example_inputs):
    inputs, text = example_inputs
    text = text.replace("0: iconst_0", "0: iconst_1")
    text = text.replace("2: iload_0\n       3: ifne          8", "2: goto          8")
    for query in inputs["queries"]:
        query["target"]["instruction_index"] = 3
    results = run_a.analyse(inputs, text, seed=0, random_trials=0)
    assert {result["verdict"] for result in results} == {"unknown"}
    assert all(result["witness"] is None for result in results)


def test_answer_metadata_does_not_influence_a(example_inputs):
    inputs, text = example_inputs
    expected = run_a.analyse(inputs, text, seed=0)
    poisoned = copy.deepcopy(inputs)
    for query in poisoned["queries"]:
        query.update(expected="unreachable", witness={"x": 100003}, path_condition="false")
    assert run_a.analyse(poisoned, text, seed=0) == expected


def test_random_hit_is_reported_with_its_witness_and_phase(example_inputs, monkeypatch):
    inputs, text = example_inputs
    rng = random.Random(0)
    monkeypatch.setattr(rng, "randint", lambda low, high: 17)
    monkeypatch.setattr(run_a.random, "Random", lambda seed: rng)
    monkeypatch.setattr(run_a, "execute_bytecode", lambda method, args: (0, args == (17,)))
    results = run_a.analyse(inputs, text, seed=0)
    assert all(result["verdict"] == "reachable" and result["witness"] == [17] for result in results)
    assert all(result["witness_phase"] == "random" for result in results)
    assert all(result["fixed_trials"] == 9 and result["random_trials"] == 1 for result in results)


@pytest.mark.parametrize("field", ["instruction_index", "jvm_byte_offset", "line"])
def test_a_rejects_bad_target_mappings(example_inputs, field):
    inputs, text = example_inputs
    inputs["queries"][0]["target"][field] = -1
    with pytest.raises(ValueError):
        run_a.analyse(inputs, text, seed=0)


def test_a_rejects_unsupported_bytecode_before_search(example_inputs):
    inputs, text = example_inputs
    text = text.replace("0: iconst_0", "0: invokestatic")
    with pytest.raises(ValueError, match="Unsupported"):
        run_a.analyse(inputs, text, seed=0)


@pytest.fixture
def prepared_main(prepared_build, monkeypatch):
    monkeypatch.setattr(run_a, "BUILD", prepared_build[0])
    return prepared_build


def test_fresh_seed_is_generated_recorded_and_replayable(prepared_main, monkeypatch):
    build, _, _ = prepared_main
    generated = iter([17, 23])

    def fresh(bits):
        assert bits == 64
        return next(generated)

    monkeypatch.setattr(run_a.secrets, "randbits", fresh)
    run_a.main([])
    first = json.loads((build / "a-results.json").read_text())
    run_a.main([])
    second = json.loads((build / "a-results.json").read_text())
    run_a.main(["--seed", str(first["seed"])])
    replay = json.loads((build / "a-results.json").read_text())
    assert first["seed"] == 17
    assert second["seed"] == 23
    assert first == replay
    assert first["random_trials_per_query"] == 1000
    assert first["fixed_seeds"] == list(FIXED_SEEDS)
    assert first["summary"] == {"reachable": 30, "unknown": 0}
    assert first["basic_sha256"]
    assert first["common_sha256"]


@pytest.mark.parametrize("change", ["class", "source", "mapping", "missing-inputs"])
def test_failed_a_run_removes_stale_success(prepared_main, change):
    build, inputs, classfile = prepared_main
    output = build / "a-results.json"
    output.write_text('{"status": "passed"}')
    if change == "class":
        classfile.write_bytes(b"changed")
    elif change == "source":
        inputs["source_sha256"] = "wrong"
    elif change == "mapping":
        inputs["queries"][0]["target"]["instruction_index"] = 5
    (build / "analysis-inputs.json").write_text(json.dumps(inputs), encoding="utf-8")
    if change == "missing-inputs":
        (build / "analysis-inputs.json").unlink()
    with pytest.raises(ValueError):
        run_a.main(["--seed", "0"])
    assert not output.exists()


def test_negative_budget_is_a_cli_error(capsys):
    with pytest.raises(SystemExit) as error:
        run_a.main(["--random-trials", "-1"])
    assert error.value.code == 2
    assert "must be nonnegative" in capsys.readouterr().err


def test_revalidation_invalidates_both_analysis_reports(tmp_path, monkeypatch):
    filenames = ("validation.json", "analysis-inputs.json", "s-results.json", "a-results.json")
    for name in filenames:
        (tmp_path / name).write_text("{}")
    monkeypatch.setattr(validate, "BUILD", tmp_path)

    def reject_metadata(*args):
        raise ValueError("Invalid metadata")

    monkeypatch.setattr(validate, "validate_metadata", reject_metadata)
    with pytest.raises(ValueError, match="Invalid metadata"):
        validate.main()
    assert all(not (tmp_path / name).exists() for name in filenames)


def test_all_real_queries_and_replay_witnesses_on_jvm(compiled_dataset):
    build, inputs, text = compiled_dataset
    results = run_a.analyse(inputs, text, seed=0)
    assert results == run_a.analyse(inputs, text, seed=0)
    hits = [result for result in results if result["verdict"] == "reachable"]
    misses = [result for result in results if result["verdict"] == "unknown"]
    assert len(hits) == 9
    assert len(misses) == 21
    assert len(results) == 30
    assert all(result["witness"] is None and result["random_trials"] == 1000 for result in misses)

    # Answer labels are used only here, after analysis, for evaluation.
    labels = json.loads((build.parent / "targets.json").read_text())["queries"]
    expected = {query["id"]: query["expected"] for query in labels}
    assert all(expected[result["id"]] == "reachable" for result in hits)
    assert sum(expected[result["id"]] == "reachable" for result in misses) == 6

    methods = validate.parse_disassembly(text, {q["method"]: q["target"]["line"] for q in inputs["queries"]})
    queries = {query["id"]: query for query in inputs["queries"]}
    requests = []
    for result in hits:
        name = queries[result["id"]]["method"]
        assert validate.execute_bytecode(methods[name], result["witness"])[1]
        requests.append(" ".join([name, *map(str, result["witness"])]))
    output = validate.run(
        ["java", "-Xint", "-cp", str(build / "classes"), "group15.validation.RuntimeCheck"],
        input="\n".join(requests) + "\n",
    )
    assert output.splitlines() == ["1"] * len(hits)


def test_real_cli_runs_with_replay_seed(compiled_dataset):
    build, _, _ = compiled_dataset
    # Run the actual CLI with an isolated build so no workspace reports are overwritten.
    entry = (
        "import sys; from pathlib import Path; "
        f"sys.path.insert(0, {str(run_a.ROOT / 'group15')!r}); "
        f"import run_a; run_a.BUILD=Path({str(build)!r}); run_a.main()"
    )
    completed = subprocess.run(
        [sys.executable, "-c", entry, "--seed", "0", "--random-trials", "1000"],
        capture_output=True, text=True, timeout=60, check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    report = json.loads((build / "a-results.json").read_text())
    assert report["summary"] == {"reachable": 9, "unknown": 21}
    assert report["seed"] == 0
    assert len(report["queries"]) == 30
