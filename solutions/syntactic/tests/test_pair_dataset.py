import copy
import json
import shutil

import pytest
import basic_search
import pair_dataset
import run_a
import run_s
import validate
from analysis_common import load_inputs
from structural import pair_verdict


def test_pair_excludes_individually_reachable_targets_on_different_paths():
    instructions = [
        {"opr": "if", "target": 3}, {"opr": "push"}, {"opr": "return"},
        {"opr": "push"}, {"opr": "return"},
    ]
    assert pair_verdict(instructions, [[1], [3]]) == "unreachable"


def test_pair_tracks_both_orders_and_terminates_on_cycles():
    instructions = [
        {"opr": "if", "target": 3}, {"opr": "push"},
        {"opr": "goto", "target": 0}, {"opr": "return"},
    ]
    assert pair_verdict(instructions, [[3], [1]]) == "unknown"
    assert pair_verdict([{"opr": "goto", "target": 0}, {"opr": "return"}],
                        [[0], [1]]) == "unreachable"


def test_pair_rejects_invalid_mapping():
    with pytest.raises(ValueError, match="Invalid target"):
        pair_verdict([{"opr": "return"}], [[0], [1]])


@pytest.mark.parametrize("instructions", [
    [(0, "fload_0", ""), (1, "ldc", "#1 // float 0.1f"),
     (3, "fadd", ""), (4, "f2i", ""), (5, "ireturn", "")],
    [(0, "iconst_1", ""), (1, "newarray", "int"), (3, "arraylength", ""),
     (4, "ireturn", "")],
    [(0, "aload_0", ""), (1, "getfield", "#1 // Field value:I"), (4, "ireturn", "")],
])
def test_s_ignores_new_values_without_expanding_a(instructions):
    method = {"instructions": instructions}
    normalized = pair_dataset.normalize(method, structural=True)
    assert pair_verdict(normalized, [[0], [len(instructions) - 1]]) == "unknown"
    with pytest.raises(pair_dataset.Unsupported, match="Unsupported opcode"):
        pair_dataset.normalize(method)


@pytest.mark.parametrize("opcode", ["ifnull", "ifnonnull", "if_acmpeq", "if_acmpne"])
def test_s_reference_conditions_keep_both_edges_and_separate_paths(opcode):
    method = {"instructions": [
        (0, opcode, "5"), (3, "iconst_1", ""), (4, "ireturn", ""),
        (5, "iconst_1", ""), (6, "ireturn", ""),
    ]}
    normalized = pair_dataset.normalize(method, structural=True)
    assert pair_verdict(normalized, [[0], [1]]) == "unknown"
    assert pair_verdict(normalized, [[0], [3]]) == "unknown"
    assert pair_verdict(normalized, [[1], [3]]) == "unreachable"


def test_s_throw_ends_path_and_handlers_remain_unsupported():
    method = {"instructions": [(0, "aconst_null", ""), (1, "athrow", ""),
                               (2, "iconst_1", ""), (3, "ireturn", "")],
              "exception_handlers": False}
    query = {"method": "example", "targets": [{"method": "example"}, {"method": "example"}]}
    normalized = pair_dataset.supported_method(query, method, structural=True)
    assert pair_verdict(normalized, [[0], [2]]) == "unreachable"
    with pytest.raises(pair_dataset.Unsupported, match="Exception handlers"):
        pair_dataset.supported_method(query, {**method, "exception_handlers": True}, structural=True)


@pytest.mark.parametrize("opcode", ["invokevirtual", "invokestatic", "invokespecial",
                                  "invokeinterface", "invokedynamic", "unknown_opcode"])
def test_s_still_rejects_calls_and_unrecognized_instructions(opcode):
    with pytest.raises(pair_dataset.Unsupported, match="Unsupported opcode"):
        pair_dataset.normalize({"instructions": [(0, opcode, "")]}, structural=True)


def test_concrete_pair_does_not_use_return_value_or_mix_runs():
    method = {
        "instructions": [
            (0, "iload_0", ""), (1, "ifeq", "8"),
            (4, "iconst_1", ""), (5, "istore_1", ""), (6, "goto", "10"),
            (8, "iconst_1", ""), (9, "istore_1", ""),
            (10, "iconst_2", ""), (11, "ireturn", ""),
        ],
        "target_indices": [[2], [5]],
    }
    assert validate.execute_bytecode(method, (0,), max_steps=100) == (2, False)
    assert validate.execute_bytecode(method, (1,), max_steps=100) == (2, False)


@pytest.mark.parametrize(("opcode", "left", "right", "expected"), [
    ("iadd", 2147483647, 1, -2147483648),
    ("idiv", -2147483648, -1, -2147483648),
    ("idiv", -7, 3, -2),
    ("irem", -7, 3, -1),
    ("iushr", -1, 33, 2147483647),
    ("ishl", 1, -1, -2147483648),
])
def test_concrete_integer_java_semantics(opcode, left, right, expected):
    method = {
        "instructions": [(0, "iload_0", ""), (1, "iload_1", ""),
                         (2, opcode, ""), (3, "ireturn", "")],
        "target_byte_offset": -1,
    }
    assert validate.execute_bytecode(method, (left, right), max_steps=100) == (expected, False)


def test_concrete_loop_cutoff_is_not_a_proof():
    method = {"instructions": [(0, "goto", "0")], "target_indices": [[1], [2]]}
    assert validate.execute_bytecode(method, (0,), max_steps=5) == (None, None)


def test_a_reports_cutoffs_and_does_not_drop_unsupported_queries(monkeypatch):
    looping = {"instructions": [(0, "goto", "0"), (3, "iconst_1", ""),
                                (4, "ireturn", "")],
               "descriptor": "(I)I", "exception_handlers": False}
    query = {"id": "loop", "method": "loop",
             "targets": [{"method": "loop", "instruction_indices": [0]},
                         {"method": "loop", "instruction_indices": [1]}]}
    monkeypatch.setattr(basic_search, "MAX_STEPS", 5)
    monkeypatch.setattr(pair_dataset, "prepared_queries", lambda inputs, text: [
        (query, looping), ({**query, "id": "exception"}, {**looping, "exception_handlers": True})])
    results = basic_search.analyse({"schema_version": 2}, "", 0, 2)
    assert results[0]["verdict"] == "unknown"
    assert results[0]["cutoff_trials"] == 11
    assert "bound" in results[0]["reason"]
    assert results[1]["verdict"] == "unsupported"
    assert "Exception" in results[1]["reason"]


def test_division_by_zero_stops_before_second_target():
    method = {"instructions": [(0, "iconst_1", ""), (1, "iconst_0", ""),
                               (2, "idiv", ""), (3, "ireturn", "")],
              "target_indices": [[0], [3]]}
    assert validate.execute_bytecode(method, (0,), max_steps=10) == (None, False)


@pytest.fixture(scope="module")
def categories(tmp_path_factory):
    if not all(shutil.which(tool) for tool in ("javac", "javap", "java")):
        pytest.skip("Real dataset integration requires JDK 17+")
    build = tmp_path_factory.mktemp("categories")
    pair_dataset.prepare(build, "categories")
    inputs, text = load_inputs(build)
    return build, inputs, text


def test_categories_inventory_pair_mappings_and_unsupported_reasons(categories):
    _, inputs, text = categories
    results = run_s.analyse(inputs, text)
    assert len(results) == 140
    assert len({result["id"] for result in results}) == 140
    assert all(len(result["targets"]) == 2 for result in results)
    by_id = {result["id"]: result for result in results}
    assert by_id["branch_14"]["verdict"] == "unreachable"
    assert by_id["branch_15"]["verdict"] == "unknown"
    assert by_id["branch_17"]["verdict"] == "unsupported"
    assert "Exception" in by_id["branch_17"]["reason"]
    assert by_id["methods_08"]["verdict"] == "unsupported"
    assert "callees" in by_id["methods_08"]["reason"]
    assert by_id["branch_01"]["verdict"] == "unknown"
    for name in [*(f"arrstr_{i:02d}" for i in range(1, 11)),
                 "edge_05", "edge_06", "edge_07", "edge_08", "edge_11", "edge_13", "edge_14"]:
        assert by_id[name]["verdict"] == "unknown", name
    assert by_id["objs_01"]["verdict"] == "unsupported"
    assert "invokespecial" in by_id["objs_01"]["reason"]


def test_pair_manifest_rejects_tampering_and_ignores_answers(categories):
    _, inputs, text = categories
    poisoned = copy.deepcopy(inputs)
    for query in poisoned["queries"]:
        query.update(expected="reachable", witness=[100003])
    assert run_s.analyse(poisoned, text) == run_s.analyse(inputs, text)
    assert run_a.analyse(poisoned, text, 0, 0) == run_a.analyse(inputs, text, 0, 0)
    poisoned["queries"][0]["targets"][0]["instruction_indices"] = [0]
    with pytest.raises(ValueError, match="mappings"):
        run_s.analyse(poisoned, text)


def test_categories_default_cli_and_replayed_witnesses_on_jvm(categories, monkeypatch):
    build, inputs, text = categories
    monkeypatch.setattr(run_s, "BUILD", build.parent)
    monkeypatch.setattr(run_a, "BUILD", build.parent)
    # Exercise the default selector while keeping output inside the pytest directory.
    destination = build.parent / "categories"
    if build != destination:
        shutil.copytree(build, destination)
    run_s.main([])
    run_a.main(["--seed", "0", "--random-trials", "0"])
    report = json.loads((destination / "a-results.json").read_text())
    assert report["dataset"] == "categories"
    assert sum(report["summary"].values()) == 140
    assert report["queries"] == run_a.analyse(inputs, text, 0, 0)
    three_arguments = next(result for result in report["queries"] if result["id"] == "branch_02")
    assert three_arguments["verdict"] == "unsupported"
    assert "arguments" in three_arguments["reason"]
    hits = [result for result in report["queries"] if result["verdict"] == "reachable"]
    assert hits
    validate.run(["javac", "-d", str(destination / "classes"),
                  str(validate.ROOT / "group15" / "validation" / "RuntimeCheck.java")])
    output = validate.run(
        ["java", "-cp", str(destination / "classes"), "group15.validation.RuntimeCheck",
         "group15.LineReachabilityCategories"],
        input="\n".join(" ".join([result["method"], *map(str, result["witness"])])
                        for result in hits) + "\n",
    )
    assert output.splitlines() == ["2"] * len(hits)
