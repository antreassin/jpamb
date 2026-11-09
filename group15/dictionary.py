"""S1: method-local integer constants and dictionary search B.

Only executable bytecode enters the extractor. Search receives a concrete
target-entry callback, never benchmark labels or known witnesses. The value
pool and tuple iterator are also available to the future shared C/D engine.
"""

import random
import re
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from itertools import islice, product
from typing import Literal

MIN_INT, MAX_INT = -(2**31), 2**31 - 1
# Same fixed prefix as A on the team's Simone branch.
FIXED_SEEDS = (0, 1, -1, 2, -2, MIN_INT, MIN_INT + 1, MAX_INT - 1, MAX_INT)
DEFAULT_DICTIONARY_TRIALS = 1000
DEFAULT_RANDOM_TRIALS = 1000


def _int32(value: object) -> int:
    if type(value) is not int or not MIN_INT <= value <= MAX_INT:
        raise ValueError(f"Expected a signed Java int, got {value!r}")
    return value


def _budget(value: int, name: str) -> None:
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a nonnegative integer")


def _arity(value: int) -> None:
    if type(value) is not int or value not in (1, 2):
        raise ValueError("B supports one or two int arguments")


def extract_jvm_constants(instructions: Iterable[dict]) -> tuple[int, ...]:
    """Read integer pushes/increments from one jvm2json bytecode list.

    This is the list at method['code']['bytecode'], not an entire class or
    stripped structural CFG. Integer iconst/bipush/sipush/ldc all become push.
    Null and noninteger pushes are ignored. Missing literal operands fail
    explicitly so an adapter cannot silently discard the dictionary.
    """
    constants = set()
    for instruction in instructions:
        if instruction.get("opr") == "push":
            if "value" not in instruction:
                raise ValueError("push is missing its literal value")
            value = instruction["value"]
            if value is None:
                continue
            if not isinstance(value, dict) or "type" not in value:
                raise ValueError("push requires a typed literal value")
            if value["type"] in ("integer", "int"):
                constants.add(_int32(value.get("value")))
        elif instruction.get("opr") == "incr":
            constants.add(_int32(instruction.get("amount")))
    return tuple(sorted(constants))


def extract_javap_constants(
    instructions: Iterable[tuple[int, str, str]],
) -> tuple[int, ...]:
    """Read the raw instruction tuples produced by validate.parse_disassembly.

    The javap adapter supports the Group 15 integer fragment, ldc_w and iinc.
    It reads the resolved `// int` value, never the constant-pool index. It
    does not parse source text, line tables, jump targets or local-slot indices.
    """
    constants = set()
    for _, opcode, operand in instructions:
        if re.fullmatch(r"iconst_(?:m1|[0-5])", opcode):
            constants.add(-1 if opcode == "iconst_m1" else int(opcode[-1]))
        elif opcode in ("bipush", "sipush"):
            if not re.fullmatch(r"-?\d+", operand.strip()):
                raise ValueError(f"Malformed {opcode} operand: {operand!r}")
            constants.add(_int32(int(operand)))
        elif opcode in ("ldc", "ldc_w"):
            match = re.fullmatch(r"#\d+\s+// int (-?\d+)\s*", operand)
            if match:
                constants.add(_int32(int(match[1])))
            elif not re.fullmatch(r"#\d+\s+// (?!int\b)\S+.*", operand):
                raise ValueError(f"Expected a resolved javap ldc operand: {operand!r}")
        elif opcode in ("iinc", "iinc_w"):
            match = re.fullmatch(r"\d+,\s*(-?\d+)", operand.strip())
            if not match:
                raise ValueError(f"Malformed iinc operand: {operand!r}")
            constants.add(_int32(int(match[1])))
    return tuple(sorted(constants))


def dictionary_values(constants: Iterable[int]) -> tuple[int, ...]:
    """A's seeds, followed by sorted unique literals and their +/-1 neighbors.

    Out-of-range neighbors are dropped, not wrapped. Each method gets its own
    pool, including unused executable literals and bookkeeping values 0/1.
    """
    values = set()
    for constant in constants:
        constant = _int32(constant)
        values.update(
            value
            for value in (constant - 1, constant, constant + 1)
            if MIN_INT <= value <= MAX_INT
        )
    return FIXED_SEEDS + tuple(sorted(values.difference(FIXED_SEEDS)))


def dictionary_inputs(
    arity: int,
    constants: Iterable[int],
    max_trials: int = DEFAULT_DICTIONARY_TRIALS,
) -> Iterator[tuple[int, ...]]:
    """Bounded Cartesian tuples beyond A's fixed tuples, in stable order.

    Mixed tuples (one fixed value, one extracted value) and equal pairs are
    included. The Cartesian product is lazy; it is never materialized. This
    iterator is reusable by D, but does not implement a coverage scheduler.
    """
    _arity(arity)
    _budget(max_trials, "max_trials")
    values = dictionary_values(constants)
    fixed = set(FIXED_SEEDS)
    candidates = (
        arguments
        for arguments in product(values, repeat=arity)
        if not all(value in fixed for value in arguments)
    )
    return islice(candidates, max_trials)


@dataclass(frozen=True)
class SearchResult:
    verdict: Literal["reachable", "unknown"]
    witness: tuple[int, ...] | None
    fixed_trials: int
    dictionary_trials: int
    random_trials: int


def search(
    arity: int,
    constants: Iterable[int],
    hits_target: Callable[[tuple[int, ...]], bool],
    rng: random.Random,
    dictionary_trials: int = DEFAULT_DICTIONARY_TRIALS,
    random_trials: int = DEFAULT_RANDOM_TRIALS,
) -> SearchResult:
    """B: A's fixed prefix, bounded dictionary tuples, then uniform random.

    The callback must observe target instruction entry in one concrete run.
    A miss after all trials is unknown. Exceptions propagate to the runner;
    unsupported execution must not be misreported as a reachability verdict.
    The caller seeds/owns the RNG and bounds execution of each callback.
    """
    _budget(random_trials, "random_trials")
    candidates = dictionary_inputs(arity, constants, dictionary_trials)

    for fixed_count, arguments in enumerate(product(FIXED_SEEDS, repeat=arity), 1):
        if hits_target(arguments):
            return SearchResult("reachable", arguments, fixed_count, 0, 0)

    fixed_count = len(FIXED_SEEDS) ** arity
    dictionary_count = 0
    for dictionary_count, arguments in enumerate(candidates, 1):
        if hits_target(arguments):
            return SearchResult(
                "reachable", arguments, fixed_count, dictionary_count, 0
            )

    for random_count in range(1, random_trials + 1):
        arguments = tuple(rng.randint(MIN_INT, MAX_INT) for _ in range(arity))
        if hits_target(arguments):
            return SearchResult(
                "reachable", arguments, fixed_count, dictionary_count, random_count
            )

    return SearchResult("unknown", None, fixed_count, dictionary_count, random_trials)
