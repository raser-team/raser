import math
from types import SimpleNamespace

import pytest

from raser.core.deposit.along_beam import parse_along_beam
from raser.core.deposit.generation import GENERATED_LIMIT
from raser.core.deposit.simulate_deposits import simulate_deposits
from raser.core.deposit.simulate_deposits import g4_configuration
from raser.core.deposit.simulate_deposits import generated_fraction
from raser.core.deposit.simulate_deposits import tilted
from raser.core.deposit.simulate_deposits import world_half_side
from raser.core.deposit.simulate_deposits import WORLD_HALF_SIDE

SOURCE = {
    "name": "pion",
    "kind": "beam",
    "par_type": "pi-",
    "par_energy": 1000.0,
}
# the source is 1 mm in front of the device and aims through its front face
G4SETUP = {
    "name": "time_resolution",
    "geant4_model": "time_resolution",
    "total_events": 10000,
    "objects": {},
    "world": "G4_Galactic",
    "maxstep": 2,
    "g4_vis": False,
    "par_energy": 5.0,
    "source": {"angle": 0},
    "along_beam": ["source", {"gap": 1000}, {"slot": "Device"}],
}
SLAB = SimpleNamespace(l_x=100.0, l_y=100.0, l_z=50.0, material="Si")
DEVICES = {"Device": SLAB}
WINDOWS = {"Device": (None, None)}


def _layout(setup=G4SETUP, devices=DEVICES):
    return parse_along_beam(setup, devices)


def _configuration(source=SOURCE, setup=G4SETUP, events=1, windows=WINDOWS, **more):
    return g4_configuration(source, setup, _layout(setup), events, windows, "all", None, **more)


def test_experiment_overrides_source_overrides_g4setup() -> None:
    configuration = _configuration(events=3, windows={"Device": (None, 0.1)})

    # of the experiment, whatever the files say
    # 3 events to record, generated until there are that many
    assert configuration["recorded_events"] == 3
    assert configuration["total_events"] == GENERATED_LIMIT
    counted = _configuration(events=None, generated=5)
    assert (counted["recorded_events"], counted["total_events"]) == (None, 5)
    assert configuration["windows"] == {"Device": (None, 0.1)}
    assert configuration["require"] == "all" and configuration["coincidence_window_ns"] is None
    # the particle is of the source
    assert configuration["par_energy"] == 1000.0
    # the surroundings are of the g4setup; the names of the files are gone
    assert configuration["geant4_model"] == "time_resolution"
    assert configuration["objects"] == {}
    assert "name" not in configuration and "kind" not in configuration
    # the source is at the origin and aims at the front face of the first slot
    assert configuration["par_in"] == [0, 0, 0] and configuration["par_out"] == [0, 0, 1000]
    with pytest.raises(ValueError, match="par_in"):
        _configuration({**SOURCE, "par_in": [0, 0, 1000]})


def test_the_source_aims_at_the_front_of_the_first_slot_along_the_beam() -> None:
    setup = {**G4SETUP, "along_beam": ["source", {"gap": 300}, {"slot": "ref"}, {"slot": "dut"}]}
    devices = {"ref": SLAB, "dut": SLAB}
    layout = _layout(setup, devices)

    configuration = g4_configuration(
        SOURCE, setup, layout, 1, {"ref": (None, None), "dut": (None, None)}, "any", None
    )

    assert configuration["par_out"] == [0, 0, 300]
    # a slot right at the source leaves no direction to aim along
    touching = {**G4SETUP, "along_beam": ["source", {"slot": "Device"}]}
    with pytest.raises(ValueError, match="no direction"):
        g4_configuration(SOURCE, touching, _layout(touching), 1, WINDOWS, "all", None)


def test_source_of_an_unknown_kind_is_refused() -> None:
    with pytest.raises(ValueError, match="laser"):
        simulate_deposits(DEVICES, {"kind": "laser"}, None, 1, 0, WINDOWS, "all", None)


def test_slots_of_the_g4setup_and_the_devices_must_be_the_same() -> None:
    setup = {**G4SETUP, "along_beam": ["source", {"slot": "ref"}, {"slot": "dut"}]}
    source = {"kind": "toy_mip", "landau_sampling": False}
    with pytest.raises(ValueError, match=r"places \['ref', 'dut'\], the devices are \['Device'\]"):
        simulate_deposits(DEVICES, source, setup, 1, 0, WINDOWS, "all", None)
    with pytest.raises(ValueError, match=r"places \['Device'\], the devices are \['ref', 'dut'\]"):
        simulate_deposits(
            {"ref": SLAB, "dut": SLAB}, source, None, 1, 0,
            {"ref": (None, None), "dut": (None, None)}, "any", None,
        )


def test_conditions_that_do_not_fit_the_slots_are_refused_before_the_run() -> None:
    source = {"kind": "toy_mip", "landau_sampling": False}
    for windows, require, window, message in (
        ({"Other": (None, None)}, "all", None, "energy windows are for"),
        ({"Device": (0.5, 0.1)}, "all", None, "edep_min"),
        (WINDOWS, "Device AND Other", None, "unknown slot 'Other'"),
        (WINDOWS, "all", 0, "must be positive"),
    ):
        with pytest.raises(ValueError, match=message):
            simulate_deposits(DEVICES, source, None, 1, 0, windows, require, window)


DEVICE = SimpleNamespace(l_x=100.0, l_y=100.0, l_z=300.0, material="Si")


def test_toy_mip_takes_the_step_limit_of_the_g4setup() -> None:
    device = {"Device": DEVICE}
    source = {"kind": "toy_mip", "landau_sampling": False}

    alone = simulate_deposits(device, source, None, 1, 0, WINDOWS, "all", None)
    coarse = simulate_deposits(device, source, {**G4SETUP, "maxstep": 50}, 1, 0, WINDOWS, "all", None)

    assert len(alone.events[0].e) == 150
    assert len(coarse.events[0].e) == 6


def test_par_angle_turns_the_source_about_where_it_enters_the_device() -> None:
    # 50 um thick; the source comes along +z and enters the front face at (0, 0, 1000)
    setup = {**G4SETUP, "source": {"angle": 60}}
    layout = _layout(setup)
    placed = _configuration(setup=setup)
    turned = tilted(placed, layout)
    assert turned["par_in"] == pytest.approx([-1000 * math.sin(math.radians(60)), 0, 500])
    assert turned["par_out"] == pytest.approx([0, 0, 1000])
    assert placed["par_in"] == [0, 0, 0]
    # a source 0.5 um in front of the face stays in front of it at any angle
    close = {"par_in": [0, 0, 999.5], "par_out": [0, 0, 1500], "par_angle": 80}
    assert tilted(close, layout)["par_in"][2] < 1000.0
    with pytest.raises(ValueError, match="neither face"):
        tilted({"par_in": [0, 0, 1020], "par_out": [0, 0, 1500], "par_angle": 30}, layout)


def test_par_angle_turns_about_the_front_face_of_a_slot_that_faces_downstream() -> None:
    setup = {**G4SETUP, "along_beam": ["source", {"gap": 1000}, {"slot": "Device", "facing": "downstream"}]}
    layout = _layout(setup)
    # the front face of the device is the one at the back: the pivot is at z = 1050
    turned = tilted({"par_in": [0, 0, 0], "par_out": [0, 0, 1050], "par_angle": 90}, layout)
    assert turned["par_in"] == pytest.approx([-1050, 0, 1050])
    assert turned["par_out"] == pytest.approx([0, 0, 1050])


def test_a_g4setup_with_more_than_one_slot_tilts_no_source() -> None:
    setup = {**G4SETUP, "along_beam": ["source", {"gap": 1000}, {"slot": "ref"}, {"slot": "dut"}]}
    layout = _layout(setup, {"ref": SLAB, "dut": SLAB})
    with pytest.raises(ValueError, match="a multi-slot g4setup tilts no source"):
        tilted({"par_in": [0, 0, 0], "par_out": [0, 0, 1000], "par_angle": 10}, layout)
    # an angle of 0 is no tilt, whatever the slots
    straight = {"par_in": [0, 0, 0], "par_out": [0, 0, 1000], "par_angle": 0}
    assert tilted(straight, layout) is straight


def test_every_particle_takes_from_the_source_what_it_does_not_give() -> None:
    source = {**SOURCE, "particles": [{}, {"offset": [30, 0, 0], "par_energy": 80.0}]}
    first, second = _configuration(source)["particles"]
    assert first["par_in"] == [0, 0, 0] and first["par_energy"] == 1000.0
    assert second["par_in"] == [30, 0, 0] and second["par_energy"] == 80.0
    assert second["par_out"] == [30, 0, 1000] and second["par_type"] == "pi-"
    # par_angle turns the points of the particles with those of the source
    setup = {**G4SETUP, "source": {"angle": 90}}
    placed = _configuration(source, setup)
    assert tilted(placed, _layout(setup))["particles"][1]["par_in"] == pytest.approx([-1000, 0, 970])


def _wide(side_x, side_y=100.0, l_z=50.0):
    return SimpleNamespace(l_x=side_x, l_y=side_y, l_z=l_z, material="Si")


def _box(side_x, offset_x=0.0, side_z=10.0):
    return {
        "box": {"shape": "box", "size": [side_x, 10, side_z], "material": "G4_Al"}
    }, {"object": "box", "offset": [offset_x, 0]}


def test_world_holds_the_column_the_objects_and_the_source() -> None:
    small = {"Device": _wide(1300, 1300)}
    setup = {**G4SETUP, "along_beam": ["source", {"gap": 17000}, {"slot": "Device"}]}
    layout = _layout(setup, small)

    # what fits is the cube it always had, about the middle of the column; the
    # world is about the origin, so half the column is added
    assert world_half_side(layout, {"par_radius": 2500}) == WORLD_HALF_SIDE + layout.length / 2
    # a device wider than the world: its edge is inside, with room around
    wide = {"Device": _wide(96791)}
    assert world_half_side(_layout(setup, wide), {}) == 96791 + _layout(setup, wide).length / 2
    # an object that starts beyond the world
    objects, item = _box(2000, 29000)
    far = {**setup, "objects": objects, "along_beam": ["source", {"gap": 17000}, item, {"slot": "Device"}]}
    far_layout = _layout(far, small)
    assert world_half_side(far_layout, {}) == 60000 + far_layout.length / 2
    # a disk of a source reaches by its radius
    assert world_half_side(layout, {"par_radius": 30000}) == 60000 + layout.length / 2
    # a column longer than the cube is wide
    long = {**setup, "along_beam": ["source", {"gap": 60000}, {"slot": "Device"}]}
    long_layout = _layout(long, small)
    assert world_half_side(long_layout, {}) == 2 * (long_layout.length / 2) + long_layout.length / 2


def test_world_reaches_the_outer_radius_of_a_tube() -> None:
    small = {"Device": _wide(1300, 1300)}
    pipe = {"shape": "tube", "outer_radius": 30000, "length": 10, "material": "G4_Al"}
    setup = {
        **G4SETUP,
        "objects": {"pipe": pipe},
        "along_beam": ["source", "pipe", {"slot": "Device"}],
    }
    layout = _layout(setup, small)

    # the tube reaches 30000 um from the axis: twice that, with the half of the column
    assert world_half_side(layout, {}) == 60000 + layout.length / 2


def test_generated_fraction_is_the_solid_angle_of_the_cone() -> None:
    sr90 = {"nuclides": [[38, 90]], "par_cone": 15}
    # (1 - cos 15 degrees) / 2 of all directions
    assert generated_fraction(sr90) == pytest.approx(0.017037, rel=1e-4)
    assert generated_fraction({"nuclides": [[38, 90]]}) == 1.0
    assert generated_fraction(SOURCE) == 1.0


def test_an_event_draws_the_same_pairs_whatever_else_is_recorded() -> None:
    from raser.core import seeding

    device = {"Device": SimpleNamespace(l_x=100.0, l_y=100.0, l_z=300.0, material="Si")}
    source = {"kind": "toy_mip", "landau_sampling": True}
    runs = []
    for edep_min in (None, 0.124):  # about half of the tracks lose more
        seeding.seed_generators(4)
        deposits = simulate_deposits(
            device, source, None, None, 0, {"Device": (edep_min, None)}, "all", None, generated=40
        )
        runs.append({event.event: event.pairs for event in deposits.events})
    everything, some = runs
    # the window drops some tracks; those it keeps drew the same pairs
    assert 0 < len(some) < len(everything)
    assert all(some[number] == everything[number] for number in some)
