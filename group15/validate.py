#!/usr/bin/env python3
"""Validate Group 15 labels from restricted Java source, bytecode, and the JVM.

No external Python packages. Requires Python 3.10+ and JDK 17+ on PATH.
The benchmark is parsed independently of targets.json's labels and explanations.
This deliberately small verifier rejects syntax outside the supported fragment.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import operator
import platform
import re
import shutil
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BUILD = HERE / "build"
MIN_INT, MAX_INT = -(2**31), 2**31 - 1
COMPARISONS = {
    "==": operator.eq, "!=": operator.ne,
    "<": operator.lt, "<=": operator.le,
    ">": operator.gt, ">=": operator.ge,
}
NEGATE = {"==": "!=", "!=": "==", "<": ">=", "<=": ">", ">": "<=", ">=": "<"}
TEMPLATES = {
    "T1_exact_match", "T2_integer_gap", "T3_early_return",
    "T4_argument_order", "T5_shared_equality",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_digest(path):
    # Git may check out the same source with CRLF on Windows.
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


@dataclass(frozen=True)
class Token:
    text: str
    line: int


@dataclass
class Method:
    name: str
    params: list[str]
    body: list
    target_line: int
    constants: set[int]


class Parser:
    """Parser and scope checker, intentionally narrower than general Java."""

    def __init__(self, source):
        pattern = re.compile(
            r"\s+|//[^\n]*|/\*[\s\S]*?\*/|[A-Za-z_][A-Za-z_0-9]*|"
            r"[0-9]+|==|!=|<=|>=|[{}();,.=<>-]"
        )
        self.tokens = []
        position, line = 0, 1
        while position < len(source):
            match = pattern.match(source, position)
            require(match is not None, f"Unsupported Java syntax at line {line}")
            text = match.group()
            if not text.isspace() and not text.startswith(("//", "/*")):
                self.tokens.append(Token(text, line))
            line += text.count("\n")
            position = match.end()
        self.tokens.append(Token("<EOF>", line))
        self.index = 0
        self.params = []
        self.locals = set()
        self.target_lines = []
        self.constants = set()
        self.guard_count = 0

    def peek(self):
        return self.tokens[self.index].text

    def take(self, wanted=None):
        token = self.tokens[self.index]
        require(wanted is None or token.text == wanted,
                f"Line {token.line}: expected {wanted!r}, found {token.text!r}")
        self.index += 1
        return token

    def literal(self):
        sign = -1 if self.peek() == "-" else 1
        if sign < 0:
            self.take("-")
        token = self.take()
        require(re.fullmatch(r"0|[1-9][0-9]*", token.text) is not None,
                f"Line {token.line}: expected decimal integer literal")
        value = sign * int(token.text)
        require(MIN_INT <= value <= MAX_INT, "Integer literal outside Java int")
        return value

    def atom(self):
        if self.peek() in self.params:
            return self.take().text
        return self.literal()

    def parse(self):
        for text in ("package", "group15", ";", "public", "final", "class", "LineReachability", "{"):
            self.take(text)
        methods = {}
        while self.peek() != "}":
            for text in ("public", "static", "int"):
                self.take(text)
            name = self.take().text
            require(re.fullmatch(r"q[0-9]{2}", name), f"Unexpected method {name}")
            require(name not in methods, f"Duplicate method {name}")
            self.take("(")
            params = []
            while True:
                self.take("int")
                param = self.take().text
                require(param in ("x", "y") and param not in params, "Invalid parameters")
                params.append(param)
                if self.peek() != ",":
                    break
                self.take(",")
            self.take(")")
            require(params in (["x"], ["x", "y"]), "Expected one or two int parameters")
            self.params, self.locals = params, set()
            self.target_lines, self.constants, self.guard_count = [], set(), 0
            body = self.block()
            require(len(self.target_lines) == 1, f"{name}: expected one hit assignment")
            require(body[0][:3] == ("declare", "hit", 0), f"{name}: first statement must initialize hit=0")
            require(self.guard_count <= 2, f"{name}: more than two guards")
            methods[name] = Method(name, params, body, self.target_lines[0], set(self.constants))
        self.take("}")
        self.take("<EOF>")
        return methods

    def block(self):
        self.take("{")
        statements = []
        while self.peek() != "}":
            line = self.tokens[self.index].line
            if self.peek() == "int":
                self.take("int")
                name = self.take().text
                require(name in ("hit", "noise") and name not in self.locals,
                        f"Line {line}: only unique hit/noise locals allowed")
                self.locals.add(name)
                self.take("=")
                value = self.literal()
                require(name != "hit" or value == 0, "hit must initialize to zero")
                self.take(";")
                statements.append(("declare", name, value, line))
            elif self.peek() == "if":
                self.take("if")
                self.take("(")
                left = self.atom()
                comparison = self.take().text
                require(comparison in COMPARISONS, "Unsupported guard")
                right = self.atom()
                require(isinstance(left, str) or isinstance(right, str), "Constant-only guard")
                for atom in (left, right):
                    if isinstance(atom, int):
                        self.constants.add(atom)
                self.take(")")
                self.guard_count += 1
                yes = self.block()
                no = []
                if self.peek() == "else":
                    self.take("else")
                    no = self.block()
                statements.append(("if", (left, comparison, right), yes, no))
            elif self.peek() == "return":
                self.take("return")
                if self.peek() == "hit":
                    value = self.take("hit").text
                    require("hit" in self.locals, "Return of undeclared hit")
                else:
                    value = self.literal()
                    require(value == 0, "Only return hit or return 0 permitted")
                self.take(";")
                statements.append(("return", value))
            else:
                self.take("hit")
                require("hit" in self.locals, "Assignment to undeclared hit")
                self.take("=")
                self.take("1")
                self.take(";")
                self.target_lines.append(line)
                statements.append(("target", line))
        self.take("}")
        return statements


def value(atom, environment):
    return environment[atom] if isinstance(atom, str) else atom


def execute_source(method, arguments):
    environment = dict(zip(method.params, arguments))
    reached = False

    def block(statements):
        nonlocal reached
        for statement in statements:
            kind = statement[0]
            if kind == "declare":
                environment[statement[1]] = statement[2]
            elif kind == "target":
                reached = True
                environment["hit"] = 1
            elif kind == "return":
                return value(statement[1], environment)
            elif kind == "if":
                left, comparison, right = statement[1]
                outcome = COMPARISONS[comparison](value(left, environment), value(right, environment))
                returned = block(statement[2] if outcome else statement[3])
                if returned is not None:
                    return returned
        return None

    result = block(method.body)
    require(result in (0, 1), f"{method.name}: method must return 0 or 1")
    require(result == int(reached), f"{method.name}: return does not encode target execution")
    return result, reached


def target_paths(statements, incoming=None):
    """All syntactic paths to target, including contradictory paths."""
    active = [[]] if incoming is None else incoming
    found = []
    for statement in statements:
        if statement[0] == "target":
            found.extend(active)
        elif statement[0] == "return":
            active = []
        elif statement[0] == "if":
            left, comparison, right = statement[1]
            yes = [path + [(left, comparison, right)] for path in active]
            no = [path + [(left, NEGATE[comparison], right)] for path in active]
            yes_active, yes_found = target_paths(statement[2], yes)
            no_active, no_found = target_paths(statement[3], no)
            active = yes_active + no_active
            found.extend(yes_found + no_found)
    return active, found


def normalize_metadata_path(text):
    """Normalize the manifest's simple conjunction, including negated guards."""
    result = []
    for term in text.split("&&"):
        term = term.strip()
        negate = term.startswith("!")
        if negate:
            term = term[1:].strip()
            require(term.startswith("(") and term.endswith(")"), "Negated guard needs parentheses")
        if term.startswith("(") and term.endswith(")"):
            term = term[1:-1].strip()
        match = re.fullmatch(r"(x|y|-?(?:0|[1-9][0-9]*))\s*(==|!=|<=|>=|<|>)\s*(x|y|-?(?:0|[1-9][0-9]*))", term)
        require(match is not None, f"Unsupported metadata path condition: {text}")
        left, comparison, right = match.groups()
        left = left if left in ("x", "y") else int(left)
        right = right if right in ("x", "y") else int(right)
        result.append((left, NEGATE[comparison] if negate else comparison, right))
    return result


def representatives(constants):
    """Complete order-type representatives for at most two unchanged arguments."""
    boundaries = sorted(set(constants) | {MIN_INT, MAX_INT})
    result = set(boundaries)
    for left, right in zip(boundaries, boundaries[1:]):
        if right - left > 1:
            result.add(left + 1)
            result.add(right - 1)
    return sorted(result)


def run(command, **kwargs):
    completed = subprocess.run(command, text=True, capture_output=True, timeout=60, **kwargs)
    require(completed.returncode == 0,
            f"Command failed: {' '.join(map(str, command))}\n{completed.stdout}\n{completed.stderr}")
    return completed.stdout


def parse_disassembly(text, target_lines):
    headers = list(re.finditer(r"^  public static int (q[0-9]{2})\([^\n]*\);$", text, re.M))
    result = {}
    for index, header in enumerate(headers):
        name = header.group(1)
        end = headers[index + 1].start() if index + 1 < len(headers) else len(text)
        segment = text[header.end():end]
        require(name not in result, f"Duplicate method: {name}")
        require(name in target_lines, f"Unexpected method: {name}")
        require("Exception table:" not in segment, f"{name}: exception handlers are unsupported")
        signature = re.search(r"descriptor: (\S+)", segment)
        require(signature is not None, f"{name}: missing descriptor")
        descriptor = signature.group(1)
        require("Code:" in segment and "LineNumberTable:" in segment,
                f"{name}: missing bytecode or debug line information; compile with -g")
        code = segment.split("Code:", 1)[1].split("LineNumberTable:", 1)[0]
        instructions = []
        for match in re.finditer(r"^\s+(\d+):\s+(\S+)([^\n]*)$", code, re.M):
            instructions.append((int(match.group(1)), match.group(2), match.group(3).strip()))
        require(instructions, f"{name}: no bytecode")
        lines = [(int(line), int(offset)) for line, offset in re.findall(r"line (\d+): (\d+)", segment)]
        target_line = target_lines[name]
        target_offsets = [offset for line, offset in lines if line == target_line]
        require(len(target_offsets) == 1, f"{name}: target must map to exactly one line-table entry")
        offset = target_offsets[0]
        indices = [i for i, instruction in enumerate(instructions) if instruction[0] == offset]
        require(len(indices) == 1, f"{name}: target line has no instruction entry")
        target_index = indices[0]
        target_instruction = instructions[target_index]
        require(target_instruction[1] == "iconst_1", f"{name}: target does not start with iconst_1")
        require(target_index + 1 < len(instructions) and instructions[target_index + 1][1].startswith("istore"),
                f"{name}: target assignment store missing")
        next_lines = [start for _, start in lines if start > offset]
        require(next_lines and instructions[target_index + 1][0] < min(next_lines),
                f"{name}: store is outside target source line")
        result[name] = {
            "descriptor": descriptor, "instructions": instructions,
            "target_byte_offset": offset, "target_instruction_index": target_index,
        }
    require(set(result) == set(target_lines), "Compiled/query method inventory mismatch")
    return result


def execute_bytecode(compiled, arguments):
    """Independent concrete interpreter for only the opcodes javac uses here."""
    instructions = compiled["instructions"]
    offset_to_index = {instruction[0]: i for i, instruction in enumerate(instructions)}
    locals_ = dict(enumerate(arguments))
    stack, pc, reached = [], 0, False
    condition = {"eq": operator.eq, "ne": operator.ne, "lt": operator.lt,
                 "le": operator.le, "gt": operator.gt, "ge": operator.ge}
    for _ in range(len(instructions) + 1):
        offset, opcode, operand = instructions[pc]
        reached |= offset == compiled["target_byte_offset"]
        next_pc = pc + 1
        if opcode.startswith("iconst_"):
            stack.append(-1 if opcode == "iconst_m1" else int(opcode[-1]))
        elif opcode in ("bipush", "sipush"):
            stack.append(int(operand))
        elif opcode == "ldc":
            constant = re.fullmatch(r"#\d+\s+// int (-?\d+)", operand)
            require(constant is not None, f"Unsupported ldc: {operand}")
            stack.append(int(constant.group(1)))
        elif opcode.startswith("iload"):
            slot = int(opcode.split("_")[1]) if "_" in opcode else int(operand)
            stack.append(locals_[slot])
        elif opcode.startswith("istore"):
            slot = int(opcode.split("_")[1]) if "_" in opcode else int(operand)
            locals_[slot] = stack.pop()
        elif opcode.startswith("if_icmp"):
            right, left = stack.pop(), stack.pop()
            if condition[opcode[7:]](left, right):
                next_pc = offset_to_index[int(operand)]
        elif opcode.startswith("if") and opcode[2:] in condition:
            if condition[opcode[2:]](stack.pop(), 0):
                next_pc = offset_to_index[int(operand)]
        elif opcode == "goto":
            next_pc = offset_to_index[int(operand)]
        elif opcode == "ireturn":
            returned = stack.pop()
            require(not stack, "Nonempty stack on ireturn")
            return returned, reached
        else:
            raise ValueError(f"Unsupported bytecode opcode: {opcode}")
        require(next_pc > pc and next_pc < len(instructions), "Unexpected backward/invalid control flow")
        pc = next_pc
    raise ValueError("Bytecode execution failed to return")


def validate_metadata(metadata, source, methods):
    require(metadata["schema_version"] == 1, "Unsupported metadata version")
    require(metadata["suite_id"] == "group15-line-reachability-v1", "Unexpected suite ID")
    require(metadata["source_file"] == "group15/src/group15/LineReachability.java", "Unexpected source path")
    require(metadata["class_name"] == "group15.LineReachability", "Unexpected class name")
    require(metadata["source_sha256"] == source_digest(source), "Source hash mismatch; review labels before updating metadata")
    require(metadata["settings"] == [{"id": "C1", "c": -7}, {"id": "C2", "c": 0}, {"id": "C3", "c": 100003}],
            "Unexpected constant settings")
    queries = metadata["queries"]
    require(len(queries) == len(methods) == 30, "Expected exactly 30 queries/methods")
    require({q["method"] for q in queries} == set(methods), "Methods and metadata disagree")
    require({q["id"] for q in queries} == {f"G15-Q{i:02d}" for i in range(1, 31)}, "Invalid query IDs")
    require(Counter(q["expected"] for q in queries) == {"reachable": 15, "unreachable": 15}, "Expected 15 R and 15 U")
    groups = Counter((q["template"], q["setting"], q["expected"]) for q in queries)
    expected_groups = {(template, setting, label): 1 for template in TEMPLATES
                       for setting in ("C1", "C2", "C3") for label in ("reachable", "unreachable")}
    require(groups == expected_groups, "Expected five pairs times three settings")
    lines = source.read_text().splitlines()
    markers = re.findall(r"// TARGET: (G15-Q[0-9]{2})\s*$", source.read_text(), re.M)
    require(Counter(markers) == Counter(q["id"] for q in queries), "Target markers must occur exactly once")
    for q in queries:
        method = methods[q["method"]]
        descriptor = "(" + "I" * len(method.params) + ")I"
        require(q["parameters"] == method.params and q["descriptor"] == descriptor, f"{q['id']}: signature mismatch")
        require(q["method_id"] == f"group15.LineReachability.{method.name}:{descriptor}", "Invalid method ID")
        require(q["target"] == {"marker": q["id"], "line": method.target_line, "statement": "hit = 1;"},
                f"{q['id']}: target metadata mismatch")
        require(lines[method.target_line - 1].strip() == f"hit = 1; // TARGET: {q['id']}", "Target must be alone on line")
        require(isinstance(q["rationale"], str) and q["rationale"].strip(), "Missing rationale")
        require(isinstance(q["path_condition"], str) and q["path_condition"].strip(), "Missing path condition")
        witness = q["witness"]
        if q["expected"] == "reachable":
            require(isinstance(witness, dict) and set(witness) == set(method.params), "Invalid witness parameters")
            require(all(type(v) is int and MIN_INT <= v <= MAX_INT for v in witness.values()), "Invalid witness integer")
        else:
            require(witness is None, "Unreachable target must not have a witness")


def main():
    # A failed rerun must never leave a previous successful report/input mapping.
    for generated in ("validation.json", "analysis-inputs.json", "s-results.json"):
        (BUILD / generated).unlink(missing_ok=True)
    metadata_path = HERE / "targets.json"
    metadata = json.loads(metadata_path.read_text())
    source = HERE / "src" / "group15" / "LineReachability.java"
    methods = Parser(source.read_text()).parse()
    validate_metadata(metadata, source, methods)
    for tool in ("javac", "java", "javap"):
        require(shutil.which(tool), f"{tool} is required; install/use JDK 17 or later")
    classes = BUILD / "classes"
    classes.mkdir(parents=True, exist_ok=True)
    harness = HERE / "validation" / "RuntimeCheck.java"
    compiler_command = ["javac", "-g", "--release", "17", "-d", str(classes), str(source), str(harness)]
    run(compiler_command)
    disassembly = run(["javap", "-classpath", str(classes), "-c", "-l", "-p", "-s", metadata["class_name"]])
    (BUILD / "LineReachability.javap.txt").write_text(disassembly)
    bytecode = parse_disassembly(disassembly, {name: method.target_line for name, method in methods.items()})
    requests, expected_results, report_queries = [], [], []
    for q in metadata["queries"]:
        method = methods[q["method"]]
        require(bytecode[method.name]["descriptor"] == q["descriptor"], "Compiled descriptor mismatch")
        reps = representatives(method.constants)
        inputs = list(itertools.product(reps, repeat=len(method.params)))
        witness = q["witness"]
        if witness is not None:
            witness_tuple = tuple(witness[p] for p in method.params)
            if witness_tuple not in inputs:
                inputs.append(witness_tuple)
        hit_inputs, miss_inputs = [], []
        for arguments in inputs:
            result = execute_source(method, arguments)
            require(execute_bytecode(bytecode[method.name], arguments) == result,
                    f"{q['id']}: bytecode/source target trace mismatch for {arguments}")
            (hit_inputs if result[1] else miss_inputs).append(arguments)
            requests.append(" ".join([method.name] + [str(a) for a in arguments]))
            expected_results.append(result[0])
        reachable = bool(hit_inputs)
        require(reachable == (q["expected"] == "reachable"), f"{q['id']}: label disproved")
        require(miss_inputs, f"{q['id']}: target is accidentally always reachable")
        if witness is not None:
            require(execute_source(method, witness_tuple)[1], f"{q['id']}: witness does not hit target")
        _, paths = target_paths(method.body)
        require(paths, f"{q['id']}: target has no syntactic path")
        require(paths == [normalize_metadata_path(q["path_condition"])],
                f"{q['id']}: metadata path condition disagrees with the Java source")
        report_queries.append({
            "id": q["id"], "method_id": q["method_id"], "expected": q["expected"],
            "verified": True, "target_line": method.target_line,
            "target_jvm_byte_offset": bytecode[method.name]["target_byte_offset"],
            "target_instruction_index": bytecode[method.name]["target_instruction_index"],
            "guard_constants": sorted(method.constants), "representatives": reps,
            "partition_input_count": len(reps) ** len(method.params),
            "checked_input_count_including_witness": len(inputs),
            "hitting_input_count": len(hit_inputs), "missing_input_count": len(miss_inputs),
            "witness": witness,
            "rejecting_input": dict(zip(method.params, miss_inputs[0])),
            "derived_target_paths": [" && ".join(f"({a} {op} {b})" for a, op, b in path) for path in paths],
        })
    output = run(["java", "-Xint", "-cp", str(classes), "group15.validation.RuntimeCheck"],
                 input="\n".join(requests) + "\n")
    actual_results = [int(line) for line in output.splitlines()]
    require(actual_results == expected_results, "JVM return values disagree with source/bytecode validation")
    versions = {}
    for tool in ("javac", "java", "javap"):
        proc = subprocess.run([tool, "-version"], text=True, capture_output=True, timeout=15)
        require(proc.returncode == 0, f"Could not identify {tool} version")
        versions[tool] = (proc.stdout + proc.stderr).strip()
    report = {
        "schema_version": 1, "suite_id": metadata["suite_id"], "status": "passed",
        "source_sha256": digest(source), "metadata_sha256": digest(metadata_path),
        "validator_sha256": digest(Path(__file__)), "harness_sha256": digest(harness),
        "class_sha256": digest(classes / "group15" / "LineReachability.class"),
        "python_version": platform.python_version(), "tools": versions,
        "compile_flags": ["-g", "--release", "17"], "runtime_flags": ["-Xint"],
        "query_count": len(report_queries), "reachable": 15, "unreachable": 15,
        "source_and_bytecode_executions_each": len(requests), "jvm_invocations": len(requests),
        "full_domain_argument": (
            "All guards compare unchanged arguments with integer constants or each other. "
            "Every guard constant and both int extremes are singleton representatives. "
            "Each nonempty open interval between these constants has up to two distinct "
            "representatives. For at most two arguments their Cartesian product realizes "
            "all possible weak orderings within each interval, including equality and both "
            "strict orders. Therefore every possible comparison truth pattern over all "
            "signed 32-bit inputs is represented. Source target traces are exhaustive for "
            "this verified fragment; each is cross-checked with a separate concrete bytecode "
            "interpreter and JVM return values. This is not general Java verification."
        ),
        "offset_convention": (
            "target_jvm_byte_offset is the raw classfile byte offset reported by javap. "
            "target_instruction_index is its zero-based index in the disassembled instruction "
            "sequence. JPAMB uses instruction indices; confirm this index against the "
            "exact jvm2json output before integrating an analyser."
        ),
        "queries": report_queries,
    }
    (BUILD / "validation.json").write_text(json.dumps(report, indent=2) + "\n")
    inputs_only = {
        "schema_version": 1, "suite_id": metadata["suite_id"],
        "source_file": metadata["source_file"], "source_sha256": digest(source),
        "class_sha256": report["class_sha256"],
        "compile_flags": report["compile_flags"],
        "offset_convention": report["offset_convention"],
        "class_name": metadata["class_name"],
        "queries": [{
            "id": q["id"], "method": q["method"], "method_id": q["method_id"],
            "descriptor": q["descriptor"], "parameters": q["parameters"],
            "target": {
                **q["target"],
                "jvm_byte_offset": bytecode[q["method"]]["target_byte_offset"],
                "instruction_index": bytecode[q["method"]]["target_instruction_index"],
            },
        } for q in metadata["queries"]],
    }
    (BUILD / "analysis-inputs.json").write_text(json.dumps(inputs_only, indent=2) + "\n")
    print(f"PASS: 30 queries (15 reachable, 15 unreachable); {len(requests)} inputs checked by source, bytecode, and JVM.")
    print("All 30 target assignments retained and mapped in bytecode; every reachable has a rejecting input.")
    print(f"Report: {BUILD / 'validation.json'}")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, IndexError, OSError, subprocess.TimeoutExpired) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
