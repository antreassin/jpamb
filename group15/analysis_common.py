"""Shared, answer-free loading and target checks for the Group 15 analyses."""

import json
import re
import sys
from pathlib import Path

from validate import BUILD, ROOT, digest, parse_disassembly, require, run

sys.path.insert(0, str(ROOT / "solutions" / "syntactic" / "src"))
from structural import build_cfg


def normalize_instructions(instructions: list[tuple[int, str, str]]) -> list[dict]:
    """Adapt existing javap-loader output to S's instruction-list representation."""
    offsets = [offset for offset, _, _ in instructions]
    require(offsets and offsets[0] == 0 and offsets == sorted(set(offsets)),
            "Bytecode offsets must be unique, increasing and start at zero")
    indices = {offset: index for index, offset in enumerate(offsets)}
    normalized = []
    for offset, opcode, operand in instructions:
        instruction = {"offset": offset}
        if opcode == "goto" or re.fullmatch(r"if(?:_icmp)?(?:eq|ne|lt|le|gt|ge)", opcode):
            byte_target = int(operand)
            require(byte_target in indices, f"Jump at byte offset {offset} has no target instruction")
            instruction["opr"] = "goto" if opcode == "goto" else (
                "if" if opcode.startswith("if_icmp") else "ifz"
            )
            # javap jumps use byte offsets; S jumps use instruction-list indices.
            instruction["target"] = indices[byte_target]
        elif opcode == "ireturn":
            instruction["opr"] = "return"
        elif re.fullmatch(r"iload(?:_[0-3])?", opcode):
            instruction["opr"] = "load"
        elif re.fullmatch(r"istore(?:_[0-3])?", opcode):
            instruction["opr"] = "store"
        elif re.fullmatch(r"iconst_(?:m1|[0-5])", opcode) or opcode in {"bipush", "sipush", "ldc"}:
            instruction["opr"] = "push"
        else:
            raise ValueError(f"Unsupported Group 15 opcode at byte offset {offset}: {opcode}")
        normalized.append(instruction)

    graph = build_cfg(normalized)
    require(all(target > index for index, targets in enumerate(graph) for target in targets),
            "Group 15 methods must be loop-free with forward-only control flow")
    return normalized


def prepare_queries(inputs: dict, disassembly: str) -> list[tuple[dict, dict, list[dict]]]:
    """Validate every query before either analysis starts."""
    require(inputs["schema_version"] == 1, "Unsupported analysis input schema")
    require(inputs["suite_id"] == "group15-line-reachability-v1", "Unexpected suite ID")
    require(inputs["class_name"] == "group15.LineReachability", "Unexpected class name")
    queries = inputs["queries"]
    require(len(queries) == 30, "Expected exactly 30 queries")
    require({q["id"] for q in queries} == {f"G15-Q{i:02d}" for i in range(1, 31)},
            "Missing or duplicate query IDs")
    require({q["method"] for q in queries} == {f"q{i:02d}" for i in range(1, 31)},
            "Missing or duplicate method names")
    for query in queries:
        require(query["id"] == f"G15-Q{query['method'][1:]}", "Query/method identity mismatch")
        require(type(query["target"]["line"]) is int and query["target"]["line"] > 0,
                f"{query['id']}: invalid source line")

    compiled = parse_disassembly(disassembly, {q["method"]: q["target"]["line"] for q in queries})
    prepared = []
    for query in queries:
        method = compiled[query["method"]]
        descriptor = method["descriptor"]
        require(descriptor in {"(I)I", "(II)I"} and descriptor == query["descriptor"],
                f"{query['id']}: unsupported or mismatched method descriptor")
        require(query["method_id"] == f"{inputs['class_name']}.{query['method']}:{descriptor}",
                f"{query['id']}: method identity mismatch")
        target = query["target"]
        require(type(target["jvm_byte_offset"]) is int
                and target["jvm_byte_offset"] == method["target_byte_offset"],
                f"{query['id']}: target byte offset disagrees with the source line")
        require(type(target["instruction_index"]) is int
                and target["instruction_index"] == method["target_instruction_index"],
                f"{query['id']}: target instruction index disagrees with the bytecode")
        instructions = normalize_instructions(method["instructions"])
        prepared.append((query, method, instructions))
    return prepared


def verify_artifacts(inputs: dict, build: Path):
    require(inputs["source_file"] == "group15/src/group15/LineReachability.java", "Unexpected source path")
    source = ROOT / inputs["source_file"]
    classfile = build / "classes" / "group15" / "LineReachability.class"
    require(digest(source) == inputs["source_sha256"], "Source changed; rerun validation")
    require(digest(classfile) == inputs["class_sha256"], "Class changed; rerun validation")


def load_inputs(build: Path = BUILD) -> tuple[dict, str]:
    input_path = build / "analysis-inputs.json"
    require(input_path.is_file(), "Run python group15/validate.py before running an analysis")
    inputs = json.loads(input_path.read_text(encoding="utf-8"))
    verify_artifacts(inputs, build)
    # Read the current class, not a possibly stale saved disassembly.
    disassembly = run(["javap", "-classpath", str(build / "classes"), "-c", "-l", "-p", "-s",
                       "group15.LineReachability"])
    return inputs, disassembly


def query_metadata(query: dict, method: dict) -> dict:
    return {
        "id": query["id"],
        "method_id": query["method_id"],
        "target_line": query["target"]["line"],
        "target_jvm_byte_offset": method["target_byte_offset"],
        "target_instruction_index": method["target_instruction_index"],
        "instruction_count": len(method["instructions"]),
    }


def report_metadata(inputs: dict, build: Path) -> dict:
    verify_artifacts(inputs, build)
    return {
        "schema_version": 1,
        "status": "passed",
        "suite_id": inputs["suite_id"],
        "source_sha256": inputs["source_sha256"],
        "class_sha256": inputs["class_sha256"],
        "inputs_sha256": digest(build / "analysis-inputs.json"),
        "loader_sha256": digest(ROOT / "group15" / "validate.py"),
        "common_sha256": digest(Path(__file__)),
    }
