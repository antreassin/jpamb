import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "group15"))
import analysis_common
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


@pytest.fixture
def prepared_build(tmp_path, monkeypatch, example_inputs):
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
    monkeypatch.setattr(analysis_common, "run", lambda command: text)
    return build, inputs, classfile


@pytest.fixture(scope="session")
def compiled_dataset(tmp_path_factory):
    if not all(shutil.which(tool) for tool in ("javac", "java", "javap")):
        pytest.skip("Real bytecode integration tests require JDK 17+ on PATH")
    dataset = tmp_path_factory.mktemp("analysis-integration") / "group15"
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
    build = dataset / "build"
    inputs = json.loads((build / "analysis-inputs.json").read_text())
    text = (build / "LineReachability.javap.txt").read_text()
    return build, inputs, text
