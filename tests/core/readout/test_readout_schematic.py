import pytest

from raser.core.readout.circuit import read_subcircuit
from raser.core.readout.schematic import _taken
from raser.core.readout.schematic import arrange
from raser.core.readout.schematic import layout
from raser.core.readout.schematic import read_hints
from raser.core.readout.schematic import value_text
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
    assert placed["C1"] == {
        "nodes": ["m", "0"],
        "ends": [(3, 0), (3, -2)],
        "wires": [],
    }
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
        "nodes": ["a", "b"],
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


def test_source_that_follows_a_voltage_is_drawn_from_there_to_its_output():
    stage = _stage(E1={"between": ["b", "0"], "follows": ["a", "0"], "gain": -3.0})

    nodes, placed = layout(stage, {"E1": "amp, shift right 2"})

    assert nodes["b"] == (4, 0)
    assert placed["E1"] == {
        "nodes": ["a", "b"],
        "ends": [(2, 0), (4, 0)],
        "wires": [[(2, 0), (0, 0)]],
    }


def test_way_to_the_output_is_the_one_through_the_amplifying_elements():
    # the feedback capacitor is the shorter way from the input to the output
    stage = _stage(
        Cf={"between": ["a", "b"], "farad": 1.0},
        R1={"between": ["m", "a"], "ohm": 1.0},
        E1={"between": ["b", "0"], "follows": ["m", "0"], "gain": -3.0},
    )

    assert arrange(stage) == {"R1": "left", "E1": "amp", "Cf": "right 4, shift up 1.5"}


def test_elements_to_ground_hang_side_by_side_and_the_way_goes_on_behind_them():
    stage = _stage(
        R1={"between": ["a", "0"], "ohm": 1.0},
        R2={"between": ["0", "a"], "ohm": 1.0},
        R3={"between": ["a", "0"], "ohm": 1.0},
        R4={"between": ["a", "b"], "ohm": 1.0},
    )

    assert arrange(stage) == {
        "R4": "right, shift right 4",
        "R1": "down",
        "R2": "up, shift right 2",
        "R3": "down, shift right 4",
    }


def test_elements_between_the_same_nodes_run_one_above_the_other():
    stage = _stage(
        R1={"between": ["a", "b"], "ohm": 1.0},
        C1={"between": ["a", "b"], "farad": 1.0},
        C2={"between": ["b", "a"], "farad": 1.0},
    )

    assert arrange(stage) == {
        "R1": "right",
        "C1": "right 2, shift up 1.5",
        "C2": "left 2, shift up 3",
    }


def test_branch_goes_up_above_all_there_is_where_nothing_stands_in_its_way():
    # the feedback, R1 up from the base and R2 to the collector, is there
    # first: the supply branch on the collector goes up beside its wire, and
    # the way to the output starts behind the branch
    stage = _stage(
        x1={"model": "T", "nodes": ["c", "a", "0"]},
        R1={"between": ["a", "m"], "ohm": 1.0},
        R2={"between": ["m", "c"], "ohm": 1.0},
        C1={"between": ["c", "b"], "farad": 1.0},
        L1={"between": ["s", "c"], "henry": 1.0},
        V1={"between": ["s", "0"], "volt": 1.0},
    )

    assert arrange(stage, {"x1": "npn"}) == {
        "x1": "npn",
        "C1": "right, shift right 2",
        "R1": "up 2",
        "R2": "right 2",
        "L1": "down 2, shift right 1",
        "V1": "down",
    }


def test_hints_of_the_file_stand():
    stage = _stage(
        R1={"between": ["a", "b"], "ohm": 1.0},
        C1={"between": ["a", "0"], "farad": 1.0},
    )
    given = {"C1": "up 3", "R1": "right 4"}

    assert arrange(stage, given) == {"R1": "right 4", "C1": "up 3"}


def test_branch_does_not_go_up_through_the_sign_of_an_element():
    # the capacitor from the input to the output runs above the middle node,
    # its sign right over it, and the way leaves no room beside
    stage = _stage(
        E1={"between": ["m", "0"], "follows": ["a", "0"], "gain": 2.0},
        E2={"between": ["b", "0"], "follows": ["m", "0"], "gain": 2.0},
        C1={"between": ["a", "b"], "farad": 1.0},
        L1={"between": ["m", "s"], "henry": 1.0},
        V1={"between": ["s", "0"], "volt": 1.0},
    )

    with pytest.raises(ValueError, match="no free place for L1"):
        arrange(stage)


def test_way_is_taken_along_a_line_and_across_the_sign_of_an_element():
    # an element from (0, 2) to (4, 2), its sign at (2, 2), and a wire
    # from (6, 0) to (6, 4)
    lines = [((0, 2), (4, 2), True), ((6, 0), (6, 4), False)]

    # along the element, and where they only touch
    assert _taken(lines, (3, 2), (5, 2))
    assert not _taken(lines, (4, 2), (6, 2))
    # up through its sign, through its lead, and short of it
    assert _taken(lines, (2, 0), (2, 4))
    assert not _taken(lines, (3, 0), (3, 4))
    assert not _taken(lines, (2, 0), (2, 1))
    # across the wire
    assert not _taken(lines, (5, 2), (8, 2))


def test_amplifier_is_passed_from_its_input_to_its_output_alone():
    # E2 gives its output on the node m: it is not on the way from a to b
    stage = _stage(
        E1={"between": ["m", "0"], "follows": ["a", "0"], "gain": 2.0},
        E2={"between": ["m", "0"], "follows": ["b", "0"], "gain": 2.0},
        R1={"between": ["m", "b"], "ohm": 1.0},
    )

    with pytest.raises(ValueError, match=r"\['E2'\]"):
        arrange(stage)


def test_instance_that_the_file_does_not_say_what_it_is_is_named():
    stage = _stage(x7={"model": "T", "nodes": ["b", "a", "0"]})

    with pytest.raises(ValueError, match="x7"):
        arrange(stage)


@pytest.mark.parametrize(
    "name",
    [
        "SantaCruz",
        "Gali52",
        "BroadBandCividec",
        "ChargeSensitiveCremat",
        "Termination50",
    ],
)
def test_stages_of_the_library_can_be_drawn(name):
    path = component_path("afe", f"{name}.cir")
    stage = read_subcircuit(path)

    nodes, placed = layout(stage, arrange(stage, read_hints(path)))

    assert set(placed) == set(stage["elements"])
    if "out" in stage["ports"]:
        assert nodes[stage["ports"]["out"]][0] > 0


def test_santa_cruz_board_is_drawn_as_its_schematic_has_it():
    path = component_path("afe", "SantaCruz.cir")

    hints = arrange(read_subcircuit(path), read_hints(path))

    # feedback above the transistor, the supply above the feedback
    assert hints["C2"] == "right 2, shift up 1.5"
    assert hints["L1"] == "up 4, shift right 1"
    assert hints["L2"] == "left, shift right 4"
