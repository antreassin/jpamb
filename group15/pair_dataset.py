"""Shared dataset loading, target mapping and instruction support checks."""

import json
import re
import shutil

from validate import ROOT, digest, require, run

DATASETS = {
    "categories": ("LineReachabilityCategories", [
        f"{category}_{number:02d}"
        for category in ("branch", "arith", "loops", "methods", "arrstr", "objs", "edge")
        for number in range(1, 21)
    ]),
    "line-reachability": ("LineReachability", [f"q{number:02d}" for number in range(1, 31)]),
}
INTEGER_BINARY = {
    "iadd", "isub", "imul", "idiv", "irem", "iand", "ior", "ixor",
    "ishl", "ishr", "iushr",
}
STRUCTURAL_FALLTHROUGH = {
    "nop", "aconst_null", "lconst_0", "lconst_1",
    "fconst_0", "fconst_1", "fconst_2", "dconst_0", "dconst_1",
    "pop", "pop2", "dup_x1", "dup_x2", "dup2", "dup2_x1", "dup2_x2", "swap",
    "i2l", "i2f", "i2d", "l2i", "l2f", "l2d",
    "f2i", "f2l", "f2d", "d2i", "d2l", "d2f",
    "lcmp", "fcmpl", "fcmpg", "dcmpl", "dcmpg",
    "land", "lor", "lxor", "lshl", "lshr", "lushr",
    "new", "newarray", "anewarray", "multianewarray", "arraylength",
    "getfield", "putfield", "getstatic", "putstatic", "instanceof", "checkcast",
}


class Unsupported(ValueError):
    """A valid benchmark uses features outside the analysis's supported scope."""


def add_dataset_argument(parser):
    parser.add_argument("--dataset", choices=DATASETS, default="categories",
                        help="benchmark dataset (default: categories)")


def source_path(dataset):
    return ROOT / "group15" / "src" / "group15" / f"{DATASETS[dataset][0]}.java"


def parse_methods(text):
    """Read javap methods, retaining switch targets and exception information."""
    headers = list(re.finditer(r"^  [^\n{}]*?([\w.$<>]+)\([^\n]*\);$", text, re.M))
    methods = {}
    for index, header in enumerate(headers):
        end = headers[index + 1].start() if index + 1 < len(headers) else len(text)
        segment = text[header.end():end]
        signature = re.search(r"descriptor: (\S+)", segment)
        require(signature is not None, f"{header.group(1)}: missing descriptor")
        if "Code:" not in segment:
            continue
        require("LineNumberTable:" in segment, "Missing debug lines; compile with -g")
        code = segment.split("Code:", 1)[1].split("LineNumberTable:", 1)[0]
        matches = list(re.finditer(r"^\s+(\d+):\s+([a-z][a-z0-9_]*)([^\n]*)$", code, re.M))
        instructions, switches = [], {}
        for i, match in enumerate(matches):
            offset, opcode, operand = int(match[1]), match[2], match[3].strip()
            instructions.append((offset, opcode, operand))
            if opcode in ("tableswitch", "lookupswitch"):
                stop = matches[i + 1].start() if i + 1 < len(matches) else len(code)
                entries = re.findall(r"^\s+(-?\d+|default):\s+(\d+)\s*$",
                                     code[match.end():stop], re.M)
                require(sum(key == "default" for key, _ in entries) == 1,
                        f"{header[1]}: missing switch default")
                switches[offset] = {key: int(target) for key, target in entries}
        require(instructions, f"{header[1]}: missing instructions")
        offsets = [offset for offset, _, _ in instructions]
        require(offsets[0] == 0 and offsets == sorted(set(offsets)), "Invalid bytecode offsets")
        name = header[1]
        require(name not in methods, f"Overloaded methods are not supported by this loader: {name}")
        methods[name] = {
            "descriptor": signature[1], "instructions": instructions, "switches": switches,
            "lines": [(int(line), int(offset))
                      for line, offset in re.findall(r"line (\d+): (\d+)", segment)],
            "exception_handlers": "Exception table:" in segment,
        }
    require(methods, "No compiled methods found")
    return methods


def discover_queries(source, methods, dataset):
    class_name, names = DATASETS[dataset]
    entries = list(re.finditer(r"^    public static int (\w+)\([^\n]*\) \{", source, re.M))
    require([entry[1] for entry in entries if entry[1] in names] == names,
            "Unexpected benchmark method inventory")
    queries = []
    for i, entry in enumerate(entries):
        if entry[1] not in names:
            continue
        stop = entries[i + 1].start() if i + 1 < len(entries) else len(source)
        region = source[entry.start():stop]
        markers = list(re.finditer(r"^[^\n]*?=\s*1;\s*// Target ([12])\s*$", region, re.M))
        require(sorted(marker[1] for marker in markers) == ["1", "2"],
                f"{entry[1]}: expected exactly two target assignments")
        targets = []
        for marker in sorted(markers, key=lambda match: match[1]):
            line = source.count("\n", 0, entry.start() + marker.start()) + 1
            owners = [(name, method) for name, method in methods.items()
                      if any(number == line for number, _ in method["lines"])]
            require(len(owners) == 1, f"{entry[1]}: ambiguous or missing target line {line}")
            owner, method = owners[0]
            offsets = sorted({offset for number, offset in method["lines"] if number == line})
            indices, assignment_offsets = [], []
            for offset in offsets:
                indices_at_offset = [j for j, instruction in enumerate(method["instructions"])
                                     if instruction[0] == offset]
                require(len(indices_at_offset) == 1, f"Target line {line}: invalid instruction offset")
                instructions = method["instructions"]
                next_lines = [start for _, start in method["lines"] if start > offset]
                stop_offset = min(next_lines) if next_lines else instructions[-1][0] + 1
                # javac may put an exception's astore before a finally assignment.
                candidates = [
                    j for j in range(indices_at_offset[0], len(instructions) - 1)
                    if instructions[j][0] < stop_offset
                    and instructions[j + 1][0] < stop_offset
                    and instructions[j][1] == "iconst_1"
                    and instructions[j + 1][1].startswith("istore")
                ]
                require(len(candidates) == 1,
                        f"Target line {line}: expected one constant-one local assignment")
                index = candidates[0]
                indices.append(index)
                assignment_offsets.append(instructions[index][0])
            targets.append({"line": line, "method": owner,
                            "jvm_byte_offsets": assignment_offsets, "instruction_indices": indices})
        name = entry[1]
        descriptor = methods[name]["descriptor"]
        queries.append({
            "id": name, "category": name.rsplit("_", 1)[0] if "_" in name else "legacy",
            "method": name, "descriptor": descriptor,
            "method_id": f"group15.{class_name}.{name}:{descriptor}",
            "targets": targets,
        })
    return queries


def prepare(build, dataset):
    build.mkdir(parents=True, exist_ok=True)
    for filename in ("validation.json", "analysis-inputs.json", "s-results.json", "a-results.json"):
        (build / filename).unlink(missing_ok=True)
    for tool in ("javac", "javap"):
        require(shutil.which(tool), f"{tool} is required; install/use JDK 17 or later")
    source = source_path(dataset)
    class_name = f"group15.{DATASETS[dataset][0]}"
    classes = build / "classes"
    classes.mkdir(exist_ok=True)
    run(["javac", "-g", "--release", "17", "-d", str(classes), str(source)])
    text = run(["javap", "-classpath", str(classes), "-c", "-l", "-p", "-s", class_name])
    methods = parse_methods(text)
    queries = discover_queries(source.read_text(encoding="utf-8"), methods, dataset)
    inputs = {
        "schema_version": 2, "suite_id": f"group15-{dataset}-pairs-v1", "dataset": dataset,
        "class_name": class_name, "source_file": source.relative_to(ROOT).as_posix(),
        "source_sha256": digest(source),
        "class_sha256": digest(classes / "group15" / f"{DATASETS[dataset][0]}.class"),
        "queries": queries,
    }
    (build / "analysis-inputs.json").write_text(json.dumps(inputs, indent=2) + "\n", encoding="utf-8")
    (build / f"{DATASETS[dataset][0]}.javap.txt").write_text(text, encoding="utf-8")
    report = {
        "status": "prepared", "suite_id": inputs["suite_id"], "query_count": len(queries),
        "target_count": 2 * len(queries), "labels_verified": False,
        "checks": "Compiled with debug lines and mapped both assignments; no label proofs.",
    }
    (build / "validation.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"PREPARED: {len(queries)} two-target queries ({dataset}); labels not verified.")
    print(f"Inputs: {build / 'analysis-inputs.json'}")


def verify_identity(inputs):
    dataset = inputs["dataset"]
    require(dataset in DATASETS, "Unexpected dataset")
    require(inputs["schema_version"] == 2
            and inputs["suite_id"] == f"group15-{dataset}-pairs-v1", "Unexpected pair schema/suite")
    require(inputs["class_name"] == f"group15.{DATASETS[dataset][0]}", "Unexpected class name")
    require(inputs["source_file"] == source_path(dataset).relative_to(ROOT).as_posix(),
            "Unexpected source path")


def prepared_queries(inputs, text):
    verify_identity(inputs)
    methods = parse_methods(text)
    expected = discover_queries(source_path(inputs["dataset"]).read_text(encoding="utf-8"),
                                methods, inputs["dataset"])
    # Extra answer labels are ignored, but every identity/mapping field must match.
    actual = [{key: query[key] for key in expected[0]} for query in inputs["queries"]]
    require(actual == expected, "Query inventory or target mappings changed; rerun validation")
    return [(query, methods[query["method"]]) for query in expected]


def normalize(method, *, structural=False):
    """Keep A's concrete opcode scope strict; S only needs normal-flow edges."""
    instructions = method["instructions"]
    indices = {offset: i for i, (offset, _, _) in enumerate(instructions)}
    normalized = []
    for offset, opcode, operand in instructions:
        if (opcode == "goto" or re.fullmatch(r"if(?:_icmp)?(?:eq|ne|lt|le|gt|ge)", opcode)
                or structural and opcode in {"goto_w", "if_acmpeq", "if_acmpne", "ifnull", "ifnonnull"}):
            require(int(operand) in indices, f"Invalid jump target at {offset}")
            instruction = {"opr": "goto" if opcode in {"goto", "goto_w"} else "if",
                           "target": indices[int(operand)]}
        elif opcode in ("tableswitch", "lookupswitch"):
            switch = method["switches"][offset]
            require(all(target in indices for target in switch.values()), "Invalid switch target")
            instruction = {"opr": "tableswitch", "default": indices[switch["default"]],
                           "targets": [indices[target] for key, target in switch.items()
                                       if key != "default"]}
        elif opcode == "ireturn":
            instruction = {"opr": "return"}
        elif (re.fullmatch(r"i(?:load|store)(?:_[0-3])?", opcode)
              or re.fullmatch(r"iconst_(?:m1|[0-5])", opcode)
              or opcode in {"bipush", "sipush", "iinc", "ineg", "i2b", "i2s", "i2c", "dup"}
              or opcode in INTEGER_BINARY):
            instruction = {"opr": "binary"}
        elif opcode == "ldc" and re.fullmatch(r"#\d+\s+// int -?\d+", operand):
            instruction = {"opr": "push"}
        elif structural and opcode in {"return", "lreturn", "freturn", "dreturn", "areturn", "athrow"}:
            instruction = {"opr": "throw" if opcode == "athrow" else "return"}
        elif structural and (
            opcode in STRUCTURAL_FALLTHROUGH
            or re.fullmatch(r"[lfda](?:load|store)(?:_[0-3])?", opcode)
            or re.fullmatch(r"[ilfdabcs]a(?:load|store)", opcode)
            or re.fullmatch(r"[lfd](?:add|sub|mul|div|rem|neg)", opcode)
        ):
            # Without handlers, an implicit exception only ends this execution.
            # Keeping the normal edge overapproximates paths; no values are evaluated.
            instruction = {"opr": "push"}
        elif (structural and opcode in {"ldc", "ldc_w", "ldc2_w"}
              and re.fullmatch(r"#\d+\s+// (?:int|float|long|double|String|class)(?: .*)?", operand)):
            instruction = {"opr": "push"}
        else:
            raise Unsupported(f"Unsupported opcode: {opcode} at byte offset {offset}")
        normalized.append(instruction)
    return normalized


def supported_method(query, method, *, structural=False):
    if method["exception_handlers"]:
        raise Unsupported("Exception handlers are not supported")
    if any(target["method"] != query["method"] for target in query["targets"]):
        raise Unsupported("Targets in callees/recursion require interprocedural analysis")
    return normalize(method, structural=structural)


