from __future__ import annotations

import builtins
import hashlib
import runpy
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from types import SimpleNamespace
from typing import Literal

from group15 import run_pairs, validate
from group15.dictionary import extract_javap_constants
from group15.pair_execution import PairMethod

REVISION = "595c81fa1707dc6e99563580626415e8e42e00c8"
DEFAULT_DEPS = run_pairs.HERE / "build" / "category-deps" / REVISION
CLASS_NAME = "group15.LineReachabilityCategories"
SOURCE = "group15/src/group15/LineReachabilityCategories.java"
HARNESS = "group15/validation/RuntimeCheck.java"
PINNED_FILES = {
    "group15/validate.py": "0e421671b8b8ce3ac09938321c09917b8fcdba0337d1dce9111a24110da80646",
    "group15/pair_dataset.py": "fc41cd9161dbdb19174777d1bc1ca48bf59b86607a44edf6b8cc38c0a6bb34f1",
    SOURCE: "1daf6d45c94689c9c353dd8ffedbfb25761ed7a8608acc72691f5a9f25285493",
    HARNESS: "d41c082ce3c26c9c89233d455f4940188efd138ba3fa289b29e87446d340d9b0",
}


def _verified_snapshot(deps: Path, build: Path) -> Path:
    build.mkdir(parents=True, exist_ok=True)
    snapshot = Path(tempfile.mkdtemp(prefix="categories-", dir=build))
    for name, expected in PINNED_FILES.items():
        data = (deps / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError(f"Fingerprint mismatch for {name} at {REVISION}")
        dest = snapshot / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    return snapshot


def _team_modules(snapshot):
    directory = snapshot / "group15"
    interpreter = SimpleNamespace(
        **runpy.run_path(
            str(directory / "validate.py"), run_name=f"{snapshot.name}.validate"
        )
    )

    # The pinned loader uses a script-local "from validate import ...".
    def team_import(name, *args, **kwargs):
        if name == "validate":
            return interpreter
        return builtins.__import__(name, *args, **kwargs)

    loader = runpy.run_path(
        str(directory / "pair_dataset.py"),
        run_name=f"{snapshot.name}.pair_dataset",
        init_globals={"__builtins__": {**vars(builtins), "__import__": team_import}},
    )
    return interpreter, SimpleNamespace(**loader)


def classify_query(loader, query, compiled) -> str | None:
    if query["descriptor"] not in run_pairs.ARITY:
        return f"Unsupported entry descriptor {query['descriptor']} (requires one or two ints)"
    try:
        loader.supported_method(query, compiled)
    except loader.Unsupported as exc:
        return str(exc)
    if any(len(t["instruction_indices"]) != 1 for t in query["targets"]):
        return "A target has multiple instruction entries"
    return None


@dataclass(frozen=True)
class CategoryMethod(PairMethod):
    switches: dict


class _InstructionFetches:
    def __init__(self, instructions):
        self.instructions = instructions
        self.pcs = []

    def __iter__(self):
        # Offset-map construction iterates; only instruction dispatch indexes by PC.
        return iter(self.instructions)

    def __len__(self):
        return len(self.instructions)

    def __getitem__(self, pc):
        item = self.instructions[pc]
        self.pcs.append(pc)
        return item


@dataclass(frozen=True)
class CategoryTrace:
    pcs: tuple[int, ...]
    status: Literal["returned", "step_limit", "exception"]
    return_value: int | None
    pair_hit: bool

    @property
    def coverage(self):
        return frozenset(self.pcs)


@dataclass
class CategorySuite:
    queries: list[dict]
    methods: dict[str, CategoryMethod]
    unsupported: dict[str, str]
    constants: dict[str, tuple[int, ...]]
    classes: Path
    source: Path
    harness: Path
    fingerprints: dict
    execute_bytecode: Callable
    preparation_seconds: float
    constant_extraction_seconds: float

    def trace(self, method, arguments, *, max_steps: int) -> CategoryTrace:
        if type(max_steps) is not int or max_steps < 0:
            raise ValueError("max_steps must be a nonnegative integer")
        run_pairs.validate_arguments(method.method_id, method.arity, arguments)
        fetches = _InstructionFetches(method.instructions)
        first, second = method.target_pcs
        # Single-target mode runs through return, exception or the instruction bound.
        compiled = {
            "instructions": fetches,
            "target_byte_offset": method.instructions[second][0],
            "switches": method.switches,
        }
        value, reached = self.execute_bytecode(compiled, arguments, max_steps=max_steps)
        if reached is None:
            status = "step_limit"
        elif value is None:
            status = "exception"
        else:
            status = "returned"
        path = iter(fetches.pcs)
        return CategoryTrace(
            tuple(fetches.pcs), status, value, first in path and second in path
        )


def prepare_categories(
    deps: Path, build: Path, *, include_constants: bool = True
) -> CategorySuite:
    started = perf_counter()
    snapshot = _verified_snapshot(deps, build)
    interpreter, loader = _team_modules(snapshot)
    source, harness = snapshot / SOURCE, snapshot / HARNESS
    classes = snapshot / "classes"
    classes.mkdir()
    validate.run(
        ["javac", "-proc:none", "-g", "--release", "17", "-d", classes, source, harness]
    )
    text = validate.run(
        ["javap", "-classpath", classes, "-c", "-l", "-p", "-s", CLASS_NAME]
    )
    parsed = loader.parse_methods(text)
    queries = loader.discover_queries(
        source.read_text(encoding="utf-8"), parsed, "categories"
    )
    methods, unsupported = {}, {}
    for query in queries:
        name = query["method"]
        code = parsed[name]
        reason = classify_query(loader, query, code)
        if reason is not None:
            unsupported[name] = reason
            continue
        first, second = (t["instruction_indices"][0] for t in query["targets"])
        methods[name] = CategoryMethod(
            query["method_id"],
            run_pairs.ARITY[query["descriptor"]],
            tuple(code["instructions"]),
            (first, second),
            code["switches"],
        )
    fingerprints = {
        "files": PINNED_FILES.copy(),
        "source_sha256": PINNED_FILES[SOURCE],
        "class_sha256": validate.digest(
            classes / "group15" / "LineReachabilityCategories.class"
        ),
    }
    preparation_seconds = perf_counter() - started
    constants = {}
    extraction_seconds = 0.0
    if include_constants:
        started = perf_counter()
        constants = {
            name: extract_javap_constants(m.instructions) for name, m in methods.items()
        }
        extraction_seconds = perf_counter() - started
    return CategorySuite(
        queries,
        methods,
        unsupported,
        constants,
        classes,
        source,
        harness,
        fingerprints,
        interpreter.execute_bytecode,
        preparation_seconds,
        extraction_seconds,
    )
