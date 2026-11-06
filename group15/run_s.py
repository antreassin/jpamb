"""Run S on the validated Group 15 queries, without reading their answer labels."""

import json
import re
import subprocess
import sys
from collections import Counter

from validate import BUILD, ROOT, digest, parse_disassembly, require, run

sys.path.insert(0, str(ROOT / "solutions" / "syntactic" / "src"))
from structural import build_cfg, verdict


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


def analyse(inputs: dict, disassembly: str) -> list[dict]:
    """Use only method identities and target locations, never expected answers."""
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
    results = []
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
        target_index = method["target_instruction_index"]
        results.append({
            "id": query["id"],
            "method_id": query["method_id"],
            "target_line": target["line"],
            "target_jvm_byte_offset": method["target_byte_offset"],
            "target_instruction_index": target_index,
            "instruction_count": len(instructions),
            "verdict": verdict(instructions, target_index),
        })
    return results


def main():
    output = BUILD / "s-results.json"
    # A failed rerun must not leave an earlier success looking current.
    output.unlink(missing_ok=True)
    input_path = BUILD / "analysis-inputs.json"
    require(input_path.is_file(), "Run python group15/validate.py before running S")
    inputs = json.loads(input_path.read_text(encoding="utf-8"))
    require(inputs["source_file"] == "group15/src/group15/LineReachability.java", "Unexpected source path")
    source = ROOT / inputs["source_file"]
    classfile = BUILD / "classes" / "group15" / "LineReachability.class"
    require(digest(source) == inputs["source_sha256"], "Source changed; rerun validation")
    require(digest(classfile) == inputs["class_sha256"], "Class changed; rerun validation")

    # Read the current class, not a possibly stale saved disassembly.
    disassembly = run(["javap", "-classpath", str(BUILD / "classes"), "-c", "-l", "-p", "-s",
                       "group15.LineReachability"])
    results = analyse(inputs, disassembly)
    require(digest(classfile) == inputs["class_sha256"], "Class changed during analysis")
    summary = {value: 0 for value in ("unreachable", "unknown")}
    summary.update(Counter(result["verdict"] for result in results))
    report = {
        "schema_version": 1,
        "analysis": "S",
        "status": "passed",
        "backend": "javap via group15.validate.parse_disassembly",
        "suite_id": inputs["suite_id"],
        "source_sha256": inputs["source_sha256"],
        "class_sha256": inputs["class_sha256"],
        "inputs_sha256": digest(input_path),
        "loader_sha256": digest(ROOT / "group15" / "validate.py"),
        "runner_sha256": digest(ROOT / "group15" / "run_s.py"),
        "structural_sha256": digest(ROOT / "solutions" / "syntactic" / "src" / "structural.py"),
        "summary": summary,
        "queries": results,
    }
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    for result in results:
        print(f"{result['id']};{result['verdict']}")
    print(f"S: {len(results)} queries; {summary['unreachable']} unreachable; {summary['unknown']} unknown")
    print(f"Report: {output}")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, IndexError, TypeError, OSError, subprocess.TimeoutExpired) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
