import copy
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "group15"))
import run_s
import validate


@pytest.fixture
def example_inputs():
    queries = []
    methods = []
    for number in range(1, 31):
        name = f"q{number:02d}"
        queries.append({
            "id": f"G15-Q{number:02d}",
            "method": name,
            "method_id": f"group15.LineReachability.{name}:(I)I",
            "descriptor": "(I)I",
            "target": {"line": number * 10, "jvm_byte_offset": 6, "instruction_index": 4},
        })
        methods.append(f"""  public static int {name}(int);
    descriptor: (I)I
    Code:
       0: iconst_0
       1: istore_1
       2: iload_0
       3: ifne          8
       6: iconst_1
       7: istore_1
       8: iload_1
       9: ireturn
    LineNumberTable:
      line {number * 10 - 1}: 0
      line {number * 10}: 6
      line {number * 10 + 1}: 8
""")
    return {
        "schema_version": 1,
        "suite_id": "group15-line-reachability-v1",
        "class_name": "group15.LineReachability",
        "queries": queries,
    }, "\n".join(methods)


def test_normalize_jump_targets_are_indices_not_byte_offsets():
    instructions = run_s.normalize_instructions([
        (0, "iload_0", ""), (1, "ifeq", "6"),
        (4, "iconst_0", ""), (5, "ireturn", ""),
        (6, "iconst_1", ""), (7, "ireturn", ""),
    ])
    assert instructions[1] == {"offset": 1, "opr": "ifz", "target": 4}
    assert run_s.verdict(instructions, 4) == "unknown"


def test_normalized_goto_can_prove_unreachable():
    instructions = run_s.normalize_instructions([
        (0, "goto", "5"), (3, "iconst_1", ""), (4, "ireturn", ""),
        (5, "iconst_0", ""), (6, "ireturn", ""),
    ])
    assert run_s.verdict(instructions, 1) == "unreachable"
    assert run_s.verdict(instructions, 3) == "unknown"


@pytest.mark.parametrize("opcode", ["invokevirtual", "athrow", "tableswitch", "iadd", "ifnull"])
def test_adapter_rejects_out_of_scope_opcodes(opcode):
    with pytest.raises(ValueError, match="Unsupported Group 15 opcode"):
        run_s.normalize_instructions([(0, opcode, "")])


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
        run_s.normalize_instructions(instructions)


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
def prepared_main(tmp_path, monkeypatch, example_inputs):
    inputs, text = example_inputs
    build = tmp_path / "build"
    classfile = build / "classes" / "group15" / "LineReachability.class"
    classfile.parent.mkdir(parents=True)
    classfile.write_bytes(b"class fixture; javap output supplied by test")
    inputs.update({
        "source_file": "group15/src/group15/LineReachability.java",
        "source_sha256": validate.digest(ROOT / "group15" / "src" / "group15" / "LineReachability.java"),
        "class_sha256": validate.digest(classfile),
    })
    (build / "analysis-inputs.json").write_text(json.dumps(inputs), encoding="utf-8")
    monkeypatch.setattr(run_s, "BUILD", build)
    monkeypatch.setattr(run_s, "run", lambda command: text)
    return build, inputs, classfile


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
def real_dataset(tmp_path_factory):
    if not all(shutil.which(tool) for tool in ("javac", "java", "javap")):
        pytest.skip("Real bytecode integration tests require JDK 17+ on PATH")
    dataset = tmp_path_factory.mktemp("s-integration") / "group15"
    for relative in (
        "validate.py", "targets.json", "src/group15/LineReachability.java",
        "validation/RuntimeCheck.java",
    ):
        destination = dataset / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / "group15" / relative, destination)
    completed = subprocess.run(
        [sys.executable, str(dataset / "validate.py")],
        text=True, capture_output=True, timeout=120, check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    inputs = json.loads((dataset / "build" / "analysis-inputs.json").read_text())
    text = (dataset / "build" / "LineReachability.javap.txt").read_text()
    return run_s.analyse(inputs, text)


@pytest.mark.parametrize("query_id", ["G15-Q01", "G15-Q02", "G15-Q13"])
def test_three_real_example_methods_are_unknown(real_dataset, query_id):
    result = next(result for result in real_dataset if result["id"] == query_id)
    assert result["verdict"] == "unknown"


def test_all_30_real_targets_are_unknown(real_dataset):
    assert len(real_dataset) == 30
    assert {result["id"] for result in real_dataset} == {f"G15-Q{i:02d}" for i in range(1, 31)}
    assert {result["verdict"] for result in real_dataset} == {"unknown"}
