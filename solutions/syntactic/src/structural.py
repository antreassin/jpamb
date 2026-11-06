"""Structural control flow over JPAMB instruction-list positions.

This first step computes graph reachability, not concrete execution or source-line
reachability. Exception-handler edges and method calls are not supported.
A graph path is not a witness that an input can execute that path.
"""

from collections import deque


def successors(index: int, instructions: list[dict]) -> list[int]:
    """Return all normal-flow successors, ignoring values and conditions."""
    if type(index) is not int or not 0 <= index < len(instructions):
        raise ValueError(f"Invalid instruction position: {index!r}")

    instruction = instructions[index]
    opcode = instruction["opr"]

    if opcode in {"return", "throw"}:
        targets = []
    elif opcode == "goto":
        targets = [instruction["target"]]
    elif opcode in {"if", "ifz"}:
        # Both branches: S ignores the guard.
        targets = [instruction["target"], index + 1]
    elif opcode == "tableswitch":
        targets = [*instruction["targets"], instruction["default"]]
    elif opcode == "lookupswitch":
        targets = [case["target"] for case in instruction["targets"]]
        targets.append(instruction["default"])
    elif opcode in {"push", "load", "store", "binary", "incr", "negate", "cast", "dup"}:
        targets = [index + 1]
    else:
        # Guessing fall-through could hide an edge and produce a false proof.
        raise NotImplementedError(f"Unsupported opcode at position {index}: {opcode!r}")

    for target in targets:
        if type(target) is not int or not 0 <= target < len(instructions):
            raise ValueError(f"Invalid successor {target!r} from position {index}")

    return list(dict.fromkeys(targets))


def build_cfg(instructions: list[dict]) -> list[list[int]]:
    """Build a graph whose entry i lists the successors of instruction i."""
    if not instructions:
        raise ValueError("Cannot build a CFG without an entry instruction")
    return [successors(index, instructions) for index in range(len(instructions))]


def reachable_instructions(instructions: list[dict]) -> set[int]:
    """Find graph-reachable positions by BFS from entry position 0.

    The caller must supply a method without exception handlers. This function
    does not validate source-line mappings or the project's full Java scope.
    """
    graph = build_cfg(instructions)
    visited = {0}
    pending = deque([0])

    while pending:
        index = pending.popleft()
        for target in graph[index]:
            if target not in visited:
                # Visit each position once, even when the graph contains a cycle.
                visited.add(target)
                pending.append(target)

    return visited