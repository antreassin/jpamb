import json
from pathlib import Path

import pytest
from structural import build_cfg, reachable_instructions, successors, verdict


def test_straight_line():
    instructions = [
        {"opr": "push", "value": {"type": "integer", "value": 1}},
        {"opr": "load", "index": 0, "type": "int"},
        {"opr": "binary", "operant": "div", "type": "int"},
        {"opr": "return", "type": "int"},
    ]

    assert build_cfg(instructions) == [[1], [2], [3], []]
    assert reachable_instructions(instructions) == {0, 1, 2, 3}


@pytest.mark.parametrize("opcode", ["if", "ifz"])
@pytest.mark.parametrize("condition", ["eq", "ne", "lt", "ge"])
def test_both_branches_ignore_condition(opcode, condition):
    instructions = [
        {"opr": opcode, "condition": condition, "target": 2},
        {"opr": "return"},
        {"opr": "return"},
    ]

    assert successors(0, instructions) == [2, 1]
    assert reachable_instructions(instructions) == {0, 1, 2}


def test_goto_uses_list_position_not_byte_offset():
    instructions = [
        {"opr": "goto", "target": 2, "offset": 0},
        {"opr": "return", "offset": 3},
        {"opr": "return", "offset": 4},
    ]

    assert build_cfg(instructions) == [[2], [], []]
    assert reachable_instructions(instructions) == {0, 2}


@pytest.mark.parametrize("opcode", ["return", "throw"])
def test_terminal_instruction_has_no_fallthrough(opcode):
    instructions = [{"opr": opcode}, {"opr": "return"}]

    assert successors(0, instructions) == []
    assert reachable_instructions(instructions) == {0}


@pytest.mark.parametrize(
    "switch",
    [
        {"opr": "tableswitch", "low": 10, "targets": [2, 3, 2], "default": 4},
        {
            "opr": "lookupswitch",
            "targets": [{"key": -10, "target": 2}, {"key": 99, "target": 3}],
            "default": 4,
        },
    ],
)
def test_switch_visits_all_cases_and_default_without_fallthrough(switch):
    instructions = [switch, *[{"opr": "return"} for _ in range(4)]]

    assert successors(0, instructions) == [2, 3, 4]
    assert reachable_instructions(instructions) == {0, 2, 3, 4}


def test_bfs_finishes_on_cycle():
    instructions = [
        {"opr": "ifz", "condition": "eq", "target": 2},
        {"opr": "goto", "target": 0},
        {"opr": "return"},
    ]

    assert reachable_instructions(instructions) == {0, 1, 2}


@pytest.mark.parametrize("target", [-1, 1, 3, True, "0"])
def test_invalid_jump_is_an_error(target):
    with pytest.raises(ValueError, match="Invalid successor"):
        reachable_instructions([{"opr": "goto", "target": target}])


@pytest.mark.parametrize("index", [-1, 1, True])
def test_invalid_position_is_an_error(index):
    with pytest.raises(ValueError, match="Invalid instruction position"):
        successors(index, [{"opr": "return"}])


def test_falling_off_method_is_an_error():
    with pytest.raises(ValueError, match="Invalid successor"):
        reachable_instructions([{"opr": "load", "index": 0}])


@pytest.mark.parametrize("opcode", ["unknown_opcode", "invoke"])
def test_unsupported_opcode_is_an_error(opcode):
    with pytest.raises(NotImplementedError, match="Unsupported opcode"):
        reachable_instructions([{"opr": opcode}, {"opr": "return"}])


def test_empty_method_is_an_error():
    with pytest.raises(ValueError, match="entry instruction"):
        reachable_instructions([])


def test_real_jpamb_divide_by_n():
    root = Path(__file__).resolve().parents[3]
    path = root / "target" / "decompiled" / "jpamb" / "cases" / "Simple.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    method = next(method for method in data["methods"] if method["name"] == "divideByN")

    assert method["code"]["exceptions"] == []
    instructions = method["code"]["bytecode"]
    assert [instruction["opr"] for instruction in instructions] == [
        "push", "load", "binary", "return"
    ]
    assert build_cfg(instructions) == [[1], [2], [3], []]
    assert reachable_instructions(instructions) == {0, 1, 2, 3}


@pytest.mark.parametrize(
    "instructions",
    [
        [{"opr": "load"}, {"opr": "return"}],
        [{"opr": "ifz", "target": 2}, {"opr": "return"}, {"opr": "return"}],
        [{"opr": "if", "target": 2}, {"opr": "return"}, {"opr": "return"}],
    ],
)
def test_graph_path_is_unknown(instructions):
    assert verdict(instructions, len(instructions) - 1) == "unknown"


def test_goto_proves_skipped_instruction_unreachable():
    instructions = [{"opr": "goto", "target": 2}, {"opr": "return"}, {"opr": "return"}]
    assert verdict(instructions, 1) == "unreachable"
    assert verdict(instructions, 2) == "unknown"


def test_return_has_no_fallthrough_for_verdict():
    assert verdict([{"opr": "return"}, {"opr": "return"}], 1) == "unreachable"


@pytest.mark.parametrize("target", [-1, 1, True, "0", None])
def test_verdict_rejects_invalid_target(target):
    with pytest.raises(ValueError, match="Invalid target"):
        verdict([{"opr": "return"}], target)


def test_verdict_rejects_empty_method():
    with pytest.raises(ValueError, match="Invalid target"):
        verdict([], 0)


def test_bad_bytecode_is_not_an_unreachable_proof():
    with pytest.raises(NotImplementedError, match="Unsupported opcode"):
        verdict([{"opr": "invoke"}, {"opr": "return"}], 1)
