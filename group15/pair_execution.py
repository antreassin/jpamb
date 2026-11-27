from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from group15 import run_pairs
from group15.validate import BytecodeTrace, resolve_target_entry, trace_bytecode


@dataclass(frozen=True)
class PairMethod:
    method_id: str
    arity: int
    instructions: tuple[tuple[int, str, str], ...]
    target_pcs: tuple[int, int]


@dataclass(frozen=True)
class PairTrace(BytecodeTrace):
    method_id: str
    pair_hit: bool

    @property
    def coverage(self) -> frozenset[int]:
        """Instruction indices within this method and build."""
        return frozenset(self.pcs)


def _target_lines(source: str) -> dict[str, dict[str, int]]:
    methods = {}
    name = None
    for number, line in enumerate(source.splitlines(), 1):
        header = re.match(r"\s*public\s+static\s+int\s+(\w+)\s*\(", line)
        if header:
            name = header[1]
            if name in methods:
                raise ValueError(f"Ambiguous source method: {name}")
            methods[name] = {}
        marker = re.fullmatch(r"\s*\w+\s*=\s*1\s*;\s*//\s*(Target [12])\s*", line)
        if marker:
            target = marker[1]
            if name is None or target in methods[name]:
                raise ValueError(f"Unexpected {target} at source line {number}")
            methods[name][target] = number
    return methods


def prepare_pair_methods(prepared: run_pairs.PreparedBenchmark) -> dict[str, PairMethod]:
    source = run_pairs.PAIR_SOURCE.read_bytes()
    if hashlib.sha256(source).hexdigest() != prepared.source_sha256:
        raise ValueError("Pair source differs from the compiled benchmark")
    markers = _target_lines(source.decode("utf-8"))
    if markers.keys() != prepared.methods.keys():
        raise ValueError("Compiled and source pair methods differ")

    methods = {}
    for name, code in prepared.methods.items():
        lines = markers[name]
        if lines.keys() != {"Target 1", "Target 2"}:
            raise ValueError(f"{name}: expected both target markers")
        _, first = resolve_target_entry(name, code.instructions, code.lines, lines["Target 1"])
        _, second = resolve_target_entry(name, code.instructions, code.lines, lines["Target 2"])
        methods[name] = PairMethod(
            f"{run_pairs.CLASS_NAME}.{name}:{code.descriptor}",
            run_pairs.ARITY[code.descriptor],
            tuple(code.instructions),
            (first, second),
        )
    return methods


def trace_candidate(method: PairMethod, arguments: tuple[int, ...], *, max_steps: int) -> PairTrace:
    """Observe instruction entries during one bounded invocation."""
    run_pairs.validate_arguments(method.method_id, method.arity, arguments)
    trace = trace_bytecode(method.instructions, arguments, max_steps=max_steps)
    first, second = method.target_pcs
    # Searching the same iterator resumes immediately after the first target.
    path = iter(trace.pcs)
    pair_hit = first in path and second in path
    return PairTrace(trace.pcs, trace.status, trace.return_value, method.method_id, pair_hit)
