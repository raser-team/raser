import pytest

from raser.core.frontend.circuit import read_subcircuit
from raser.core.frontend.schematic import layout
from raser.core.frontend.schematic import read_hints
from raser.core.frontend.schematic import value_text
from raser.supports.paths import component_path


def _stage(**elements):
    return {"ports": {"in": "a", "out": "b"}, "elements": elements}


def test_elements_follow_their_hints_from_the_input():
    stage = _stage(
        R1={"between": ["a", "m"], "ohm": 1.0},
        C1={"between": ["m", "0"], "farad": 1.0},
        R2={"between": ["m", "b"], "ohm": 1.0},
    )

    nodes, placed = layout(stage, {"R1": "right 3", "C1": "down", "R2": "up"})

    assert nodes == {"a": (0, 0), "m": (3, 0), "b": (3, 2)}
    assert placed["C1"] == {"ends": [(3, 0), (3, -2)], "wires": []}
    assert placed["R2"]["ends"] == [(3, 0), (3, 2)]


def test_element_is_put_down_from_its_second_node_where_that_one_is_known():
    # the source is written before anything reaches its node, and from the
    # supply to the input: it ends on the input
    stage = _stage(
        V1={"between": ["s", "0"], "volt": 1.0},
        L1={"between": ["s", "a"], "henry": 1.0},
    )

    nodes, placed = layout(stage, {"V1": "down", "L1": "left 3"})

    assert placed["L1"]["ends"] == [(3, 0), (0, 0)]
    assert placed["V1"]["ends"] == [(3, 0), (3, -2)]
    assert nodes["s"] == (3, 0)


def test_shifted_element_is_joined_to_its_nodes_by_wires():
    stage = _stage(
        R1={"between": ["a", "b"], "ohm": 1.0},
        C1={"between": ["a", "b"], "farad": 1.0},
    )

    _, placed = layout(stage, {"R1": "right", "C1": "right, shift up 1"})

    assert placed["C1"] == {
        "ends": [(0, 1), (2, 1)],
        "wires": [[(0, 1), (0, 0)], [(2, 1), (2, 0)]],
    }


def test_wire_to_a_node_that_is_elsewhere_goes_straight_on_then_turns():
    # the transistor has put its collector at (2, 1); the resistor ends at
    # (5, 3) and runs on to the right before it turns
    stage = _stage(
        x1={"model": "T", "nodes": ["c", "a", "0"]},
        R1={"between": ["a", "m"], "ohm": 1.0},
        R2={"between": ["m", "c"], "ohm": 1.0},
    )

    nodes, placed = layout(stage, {"x1": "npn", "R1": "up 3", "R2": "left 1"})

    assert nodes["c"] == (2, 1)
    assert placed["x1"]["ends"] == [(0, 0), (2, 1), (2, -1)]
    assert placed["R2"]["wires"] == [[(-1, 3), (2, 3), (2, 1)]]


def test_element_without_a_hint_is_named():
    stage = _stage(
        R1={"between": ["a", "b"], "ohm": 1.0},
        R7={"between": ["b", "0"], "ohm": 1.0},
    )

    with pytest.raises(ValueError, match=r"\['R7'\]"):
        layout(stage, {"R1": "right"})


def test_elements_the_input_does_not_reach_are_named():
    stage = _stage(
        R1={"between": ["a", "b"], "ohm": 1.0},
        R7={"between": ["x", "0"], "ohm": 1.0},
    )

    with pytest.raises(ValueError, match=r"\['R7'\]"):
        layout(stage, {"R1": "right", "R7": "down"})


def test_values_carry_the_prefix_of_their_size():
    assert value_text({"between": ["a", "b"], "farad": 3.3e-9}) == "3.3 nF"
    assert value_text({"between": ["a", "b"], "ohm": 1e6}) == "1 MΩ"
    assert value_text({"between": ["a", "b"], "ohm": 475.0}) == "475 Ω"
    assert value_text({"between": ["a", "b"], "henry": 47e-6}) == "47 µH"
    assert value_text({"between": ["a", "b"], "farad": 0.4e-12}) == "0.4 pF"


def test_hints_are_read_from_the_stage_alone(tmp_path):
    path = tmp_path / "Stage.cir"
    path.write_text(
        ".subckt Other 1 2\n"
        "R2 1 2 50 ; up\n"
        ".ends Other\n"
        ".subckt Stage in out\n"
        "R1 in out 50 ; right 3\n"
        "* R9 in 0 50 ; down\n"
        "C1 out 0 1p\n"
        ".ends Stage\n",
        encoding="utf-8",
    )

    assert read_hints(path) == {"R1": "right 3"}


def test_santa_cruz_board_of_the_library_can_be_laid_out():
    path = component_path("afe", "SantaCruz.cir")

    nodes, placed = layout(read_subcircuit(path), read_hints(path))

    # the supply stands to the right of the output, above it
    assert nodes["8"][0] > nodes["out"][0] and nodes["8"][1] > nodes["out"][1]
    assert set(placed) == set(read_subcircuit(path)["elements"])
