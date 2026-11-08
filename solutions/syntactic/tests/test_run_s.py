import copy
import json

import pytest
import run_s
import validate
from analysis_common import normalize_instructions


def test_normalize_jump_targets_are_indices_not_byte_offsets():
    instructions = normalize_instructions([
        (0, "iload_0", ""), (1, "ifeq", "6"),
        (4, "iconst_0", ""), (5, "ireturn", ""),
        (6, "iconst_1", ""), (7, "ireturn", ""),
    ])
    assert instructions[1] == {"offset": 1, "opr": "ifz", "target": 4}
    assert run_s.verdict(instructions, 4) == "unknown"


def test_normalized_goto_can_prove_unreachable():
    instructions = normalize_instructions([
        (0, "goto", "5"), (3, "iconst_1", ""), (4, "ireturn", ""),
        (5, "iconst_0", ""), (6, "ireturn", ""),
    ])
    assert run_s.verdict(instructions, 1) == "unreachable"
    assert run_s.verdict(instructions, 3) == "unknown"


@pytest.mark.parametrize("opcode", ["invokevirtual", "athrow", "tableswitch", "iadd", "ifnull"])
def test_adapter_rejects_out_of_scope_opcodes(opcode):
    with pytest.raises(ValueError, match="Unsupported Group 15 opcode"):
        normalize_instructions([(0, opcode, "")])


@pytest.mark.parametrize(
    ("instructions", "message"),
    [
        ([], "offsets"),
        ([(1, "ireturn", "")], "offsets"),
        ([(0, "iconst_0", ""), (0, "ireturn", "")], "offsets"),
        ([(0, "goto", "2"), (3, "ireturn", "")], "no target instruction"),
        ([(0, "goto", "0")], "forward-only"),
    ],
)
def test_adapter_rejects_invalid_graphs(instructions, message):
    with pytest.raises(ValueError, match=message):
        normalize_instructions(instructions)


def test_results_have_exactly_one_verdict_per_query(example_inputs):
    inputs, text = example_inputs
    results = run_s.analyse(inputs, text)
    assert [result["id"] for result in results] == [q["id"] for q in inputs["queries"]]
    assert len(results) == 30
    assert {result["verdict"] for result in results} == {"unknown"}
    assert {result["target_instruction_index"] for result in results} == {4}


def test_answer_labels_cannot_change_s_results(example_inputs):
    inputs, text = example_inputs
    expected = run_s.analyse(inputs, text)
    poisoned = copy.deepcopy(inputs)
    for query in poisoned["queries"]:
        query.update(expected="unreachable", witness={"x": 0}, path_condition="false")
    assert run_s.analyse(poisoned, text) == expected


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("instruction_index", 6, "instruction index"),
        ("instruction_index", True, "instruction index"),
        ("jvm_byte_offset", 4, "byte offset"),
        ("line", 9999, "line-table entry"),
        ("line", True, "invalid source line"),
    ],
)
def test_wrong_target_mapping_is_an_error(example_inputs, field, value, message):
    inputs, text = example_inputs
    inputs["queries"][0]["target"][field] = value
    with pytest.raises(ValueError, match=message):
        run_s.analyse(inputs, text)


@pytest.mark.parametrize("field", ["id", "method"])
def test_duplicate_queries_are_rejected(example_inputs, field):
    inputs, text = example_inputs
    inputs["queries"][1][field] = inputs["queries"][0][field]
    with pytest.raises(ValueError, match="duplicate"):
        run_s.analyse(inputs, text)


def test_wrong_method_descriptor_is_rejected(example_inputs):
    inputs, text = example_inputs
    inputs["queries"][0]["descriptor"] = "(II)I"
    with pytest.raises(ValueError, match="descriptor"):
        run_s.analyse(inputs, text)


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        ("LineNumberTable:", "NoDebugInformation:", "debug line"),
        ("LineNumberTable:", "Exception table:\n    LineNumberTable:", "exception handlers"),
        ("       6: iconst_1", "       6: iconst_0", "iconst_1"),
        ("       7: istore_1", "       7: ireturn", "store missing"),
        ("      line 11: 8", "      line 11: 7", "outside target"),
    ],
)
def test_invalid_target_or_bytecode_is_rejected(example_inputs, old, new, message):
    inputs, text = example_inputs
    with pytest.raises(ValueError, match=message):
        run_s.analyse(inputs, text.replace(old, new, 1))


def test_source_hash_normalizes_only_crlf(tmp_path):
    source = tmp_path / "Example.java"
    source.write_bytes(b"class Example {}\n")
    expected = validate.source_digest(source)
    source.write_bytes(b"class Example {}\r\n")
    assert validate.source_digest(source) == expected
    source.write_bytes(b"class Different {}\r\n")
    assert validate.source_digest(source) != expected


@pytest.fixture
def prepared_main(prepared_build, monkeypatch):
    monkeypatch.setattr(run_s, "BUILD", prepared_build[0])
    return prepared_build


def test_runner_writes_only_s_verdicts_and_artifact_hashes(prepared_main, capsys):
    build, inputs, _ = prepared_main
    run_s.main()
    report = json.loads((build / "s-results.json").read_text())
    assert report["status"] == "passed"
    assert report["summary"] == {"unreachable": 0, "unknown": 30}
    assert report["class_sha256"] == inputs["class_sha256"]
    assert report["backend"] == "javap via group15.validate.parse_disassembly"
    assert len(report["queries"]) == 30
    assert "30 queries; 0 unreachable; 30 unknown" in capsys.readouterr().out


@pytest.mark.parametrize("change", ["class", "source", "mapping", "missing-inputs"])
def test_failed_run_removes_stale_success(prepared_main, change):
    build, inputs, classfile = prepared_main
    output = build / "s-results.json"
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
        run_s.main()
    assert not output.exists()


@pytest.fixture(scope="module")
def real_dataset(compiled_dataset):
    _, inputs, text = compiled_dataset
    return run_s.analyse(inputs, text)


@pytest.mark.parametrize("query_id", ["G15-Q01", "G15-Q02", "G15-Q13"])
def test_three_real_example_methods_are_unknown(real_dataset, query_id):
    result = next(result for result in real_dataset if result["id"] == query_id)
    assert result["verdict"] == "unknown"


def test_all_30_real_targets_are_unknown(real_dataset):
    assert len(real_dataset) == 30
    assert {result["id"] for result in real_dataset} == {f"G15-Q{i:02d}" for i in range(1, 31)}
    assert {result["verdict"] for result in real_dataset} == {"unknown"}
