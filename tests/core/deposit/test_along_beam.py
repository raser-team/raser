import importlib.util
from types import SimpleNamespace

import pytest

from raser.core.deposit import along_beam
from raser.core.deposit.along_beam import parse_along_beam
from raser.core.deposit.along_beam import slot_names
from raser.supports.paths import app_file_path

OBJECTS = {
    "A": {"shape": "box", "size": [100, 100, 5], "material": "G4_Al"},
    "B": {"shape": "box", "size": [100, 100, 40], "material": "G4_Al"},
    "C": {"shape": "box", "size": [100, 100, 11], "material": "G4_Al"},
}


def _device(l_x=60.0, l_y=40.0, l_z=30.0):
    return SimpleNamespace(l_x=l_x, l_y=l_y, l_z=l_z)


def _setup(column):
    return {"objects": OBJECTS, "along_beam": column}


def test_fronts_of_the_time_resolution_setup_add_up_along_the_beam() -> None:
    path = app_file_path("raser_bench/timeres", "components/g4setup/time_resolution.py")
    spec = importlib.util.spec_from_file_location("time_resolution_setup", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    devices = {"ref": _device(1300, 1300, 50), "dut": _device(1300, 1300, 50)}

    layout = parse_along_beam(module.G4SETUP, devices)

    fronts = {item.name: item.z for item in (*layout.objects, *layout.slots)}
    assert fronts == {
        "Al": 1995,
        "ref": 6983.5,
        "pcb1": 7033.5,
        "dut": 16717,
        "pcb2": 16767,
    }


def test_a_list_side_by_side_takes_the_thickest_item() -> None:
    devices = {"s": _device(l_z=30)}
    # 10 gap, A 5 thick, then the slot (30) beside B (40): C behind the thickest
    column = [
        "source",
        {"gap": 10},
        "A",
        [{"slot": "s", "offset": [-200, 0]}, "B"],
        "C",
    ]
    layout = parse_along_beam(_setup(column), devices)
    assert {item.name: item.z for item in (*layout.objects, *layout.slots)} == {
        "A": 10,
        "s": 15,
        "B": 15,
        "C": 55,
    }
    assert layout.length == 66

    thick = parse_along_beam(_setup(column), {"s": _device(l_z=60)})
    assert thick.objects[-1].z == 75


def test_layers_around_the_active_one_add_to_the_thickness_of_the_slot(
    monkeypatch,
) -> None:
    monkeypatch.setattr(along_beam, "inactive_thickness", lambda device: 7.0)
    column = [
        "source",
        {"gap": 100},
        {"slot": "up"},
        {"slot": "down", "facing": "downstream"},
        "A",
    ]
    layout = parse_along_beam(
        _setup(column), {"up": _device(l_z=30), "down": _device(l_z=30)}
    )
    up, down = layout.slots

    assert (up.z, down.z, layout.objects[0].z) == (100, 137, 174)
    # upstream: the active layer first, then the other layers
    assert up.active_z == (100, 130)
    assert up.front[2] == 100
    # downstream: the other layers first, the front face behind the slot
    assert down.active_z == (144, 174)
    assert down.front[2] == 174


@pytest.mark.parametrize("rotation_z", [0, 90, 180, 270])
@pytest.mark.parametrize("facing", ["upstream", "downstream"])
def test_the_device_and_the_world_are_the_same_point_both_ways(
    facing, rotation_z
) -> None:
    layout = parse_along_beam(
        _setup(
            [
                "source",
                {"gap": 50},
                {
                    "slot": "s",
                    "facing": facing,
                    "rotation_z": rotation_z,
                    "offset": [11, -7],
                },
            ]
        ),
        {"s": _device(60, 40, 30)},
    )
    slot = layout.slots[0]
    point = (13.0, 31.0, 4.0)

    assert slot.to_device(*slot.to_world(*point)) == pytest.approx(point, abs=1e-9)
    assert slot.to_world(*slot.to_device(*point)) == pytest.approx(point, abs=1e-9)


def test_the_front_face_of_a_downstream_device_is_on_its_downstream_side() -> None:
    upstream, downstream = parse_along_beam(
        _setup(
            [
                "source",
                {"gap": 50},
                {"slot": "u"},
                {"slot": "d", "facing": "downstream"},
            ]
        ),
        {"u": _device(60, 40, 30), "d": _device(60, 40, 30)},
    ).slots

    # z = 0 of the device is the front face: upstream at the front of the slot,
    # downstream at its back, and z grows against the beam
    assert upstream.to_world(30, 20, 0) == (0, 0, 50)
    assert upstream.to_world(30, 20, 10) == (0, 0, 60)
    assert downstream.to_world(30, 20, 0) == (0, 0, 110)
    assert downstream.to_world(30, 20, 10) == (0, 0, 100)
    # x turns over with it, y does not
    assert downstream.to_world(40, 25, 0) == (-10, 5, 110)


def test_rotation_about_z_turns_the_device_about_the_middle_of_its_face() -> None:
    slot = parse_along_beam(
        _setup(
            ["source", {"gap": 50}, {"slot": "s", "rotation_z": 90, "offset": [5, 1]}]
        ),
        {"s": _device(60, 40, 30)},
    ).slots[0]

    # +x of the device runs along +y of the world
    assert slot.to_world(40, 20, 0) == (5, 11, 50)
    assert slot.to_world(30, 30, 0) == (-5, 1, 50)
    # the footprint swaps its sides
    assert slot.side == (40, 60)


@pytest.mark.parametrize(
    ("column", "message"),
    [
        ([{"gap": 5}, {"slot": "s"}], "first item of along_beam must be 'source'"),
        (["source", {"gap": -1}, {"slot": "s"}], "gap must be non-negative"),
        (["source", "Z", {"slot": "s"}], "object 'Z' is not in objects"),
        (["source", "A", "A", {"slot": "s"}], "duplicate 'A' in along_beam"),
        (["source", {"slot": "s"}, {"slot": "s"}], "duplicate 's' in along_beam"),
        (["source", {"slot": "s", "facing": "left"}], "slot 's' has facing 'left'"),
        (["source", {"slot": "s", "rotation_z": 45}], "slot 's' has rotation_z 45"),
        (["source", [{"slot": "s"}, "A"]], "side-by-side items overlap"),
        (["source", {"slot": "s"}, {"slot": "t"}], r"the g4setup places \['s', 't'\]"),
    ],
)
def test_a_column_that_cannot_be_laid_out_is_refused(column, message) -> None:
    with pytest.raises(ValueError, match=message):
        parse_along_beam(_setup(column), {"s": _device()})


def test_items_side_by_side_may_touch_but_not_overlap() -> None:
    devices = {"s": _device(60, 40, 30)}
    # the slot spans x -30..30 and A is 100 wide: centres 80 apart touch, 79 apart overlap
    touching = parse_along_beam(
        _setup(["source", [{"slot": "s"}, {"object": "A", "offset": [80, 0]}]]), devices
    )
    assert len(touching.objects) == 1
    with pytest.raises(ValueError, match="overlap"):
        parse_along_beam(
            _setup(["source", [{"slot": "s"}, {"object": "A", "offset": [79, 0]}]]),
            devices,
        )


def test_the_slots_are_named_in_the_order_of_the_column() -> None:
    column = ["source", {"slot": "second"}, "A", {"slot": "first"}]
    assert slot_names(_setup(column)) == ["second", "first"]


def test_a_tube_takes_its_length_along_z_and_its_diameter_across() -> None:
    objects = {
        **OBJECTS,
        "pipe": {
            "shape": "tube",
            "inner_radius": 10,
            "outer_radius": 30,
            "length": 200,
            "material": "G4_Al",
        },
    }
    devices = {"s": _device()}
    layout = parse_along_beam(
        {"objects": objects, "along_beam": ["source", "A", "pipe", {"slot": "s"}]}, devices
    )

    pipe = layout.objects[1]
    # A takes size[2] = 5 and the pipe its length, 200
    assert pipe.z == 5
    assert layout.slots[0].z == 205
    assert pipe.thickness == 200
    # the width is twice the outer radius, not the inner one nor the radius
    assert pipe.side == (60, 60)


_BOX = {"shape": "box", "size": [100, 80, 10], "material": "G4_Al"}
_TUBE = {"shape": "tube", "outer_radius": 30, "length": 200, "material": "G4_Al"}


@pytest.mark.parametrize(
    ("objects", "materials", "message"),
    [
        ({"x": {**_BOX, "shape": "sphere"}}, {}, "object 'x' has unknown shape 'sphere'"),
        ({"x": {"shape": "box", "material": "G4_Al"}}, {}, "object 'x' is missing required key 'size'"),
        ({"x": {"shape": "tube", "length": 5, "material": "G4_Al"}}, {}, "missing required key 'outer_radius'"),
        ({"x": {"shape": "tube", "outer_radius": 5, "material": "G4_Al"}}, {}, "missing required key 'length'"),
        ({"x": {"shape": "box", "size": [1, 1, 1]}}, {}, "missing required key 'material'"),
        ({"x": {**_BOX, "size": [100, 0, 10]}}, {}, "dimensions of object 'x' must be positive"),
        ({"x": {**_TUBE, "length": -1}}, {}, "dimensions of object 'x' must be positive"),
        ({"x": {**_BOX, "hole": 0}}, {}, "dimensions of object 'x' must be positive"),
        ({"x": {**_BOX, "hole": 40}}, {}, r"hole radius \(40 um\) of object 'x' must be less than half"),
        ({"x": {**_BOX, "hole": 39}}, {}, None),
        ({"x": {**_TUBE, "inner_radius": 30}}, {}, r"inner_radius \(30 um\) of object 'x' must be less than outer_radius \(30 um\)"),
        ({"x": {**_TUBE, "inner_radius": 29}}, {}, None),
        ({"x": {**_BOX, "material": "SiO2"}}, {}, "unknown material 'SiO2' for object 'x'"),
        ({"x": {**_BOX, "material": "SiO2"}}, {"SiO2": {"density": 2.2, "elements": {"Si": 1, "O": 2}}}, None),
        ({}, {"X": {"density": 0, "elements": {"Si": 1}}}, "density of material 'X' must be positive"),
        ({}, {"X": {"density": 1, "elements": {"Si": 0}}}, "element share of 'Si' in material 'X' must be positive"),
    ],
)
def test_objects_and_materials_that_cannot_be_built_are_refused(objects, materials, message) -> None:
    setup = {
        "objects": objects,
        "materials": materials,
        "along_beam": ["source", {"slot": "s"}],
    }
    if message is None:
        parse_along_beam(setup, {"s": _device()})
        return
    with pytest.raises(ValueError, match=message):
        parse_along_beam(setup, {"s": _device()})
