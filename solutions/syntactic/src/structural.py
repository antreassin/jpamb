"""S: ignore values and conditions; look for a graph path through both targets.

No such path proves unreachable. A graph path only gives unknown, not a witness.
Source/bytecode loading and unsupported-feature checks belong to the helpers.
"""

from collections import deque
from typing import Literal


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


def verdict(instructions: list[dict], target_index: int) -> Literal["unreachable", "unknown"]:
    """Prove unreachability only when the CFG has no path to a valid target."""
    if type(target_index) is not int or not 0 <= target_index < len(instructions):
        raise ValueError(f"Invalid target instruction position: {target_index!r}")

    # A graph path may require contradictory guards, so it is not a witness.
    if target_index in reachable_instructions(instructions):
        return "unknown"
    return "unreachable"


def pair_verdict(instructions: list[dict], targets: list[list[int]]) -> Literal["unreachable", "unknown"]:
    """Track each path's two target hits, including across loops, in either order."""
    graph = build_cfg(instructions)
    if len(targets) != 2 or not all(targets):
        raise ValueError("Expected two nonempty target sets")
    if any(type(pc) is not int or not 0 <= pc < len(graph) for group in targets for pc in group):
        raise ValueError("Invalid target instruction position")

    pending, visited = deque([(0, False, False)]), set()
    while pending:
        pc, first_seen, second_seen = pending.popleft()
        first_seen = first_seen or pc in targets[0]
        second_seen = second_seen or pc in targets[1]
        if first_seen and second_seen:
            return "unknown"
        state = (pc, first_seen, second_seen)
        if state not in visited:
            visited.add(state)
            pending.extend((successor, first_seen, second_seen) for successor in graph[pc])
    return "unreachable"


def analyse(inputs: dict, disassembly: str) -> list[dict]:
    """Apply S to each query, retaining explicit unsupported results."""
    from analysis_common import prepare_queries, query_metadata
    from pair_dataset import Unsupported, prepared_queries, supported_method

    if inputs["schema_version"] != 2:
        return [
            {**query_metadata(query, method),
             "verdict": verdict(instructions, method["target_instruction_index"])}
            for query, method, instructions in prepare_queries(inputs, disassembly)
        ]

    results = []
    for query, method in prepared_queries(inputs, disassembly):
        result = dict(query)
        try:
            instructions = supported_method(query, method, structural=True)
        except Unsupported as exc:
            result.update(verdict="unsupported", reason=str(exc))
        else:
            result["verdict"] = pair_verdict(
                instructions, [target["instruction_indices"] for target in query["targets"]])
        results.append(result)
    return results