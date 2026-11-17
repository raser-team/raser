import math
from types import SimpleNamespace

import pytest

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
# 1 mm above the top face, aimed down through the device
PLACEMENT = {"at": [0, 0, -1000], "towards": [0, 0, 1000], "angle": 0}
G4SETUP = {
    "name": "time_resolution",
    "geant4_model": "time_resolution",
    "total_events": 10000,
    "edep_min": 9.0,
    "object": {"elemental": {}},
    "world": "G4_Galactic",
    "maxstep": 2,
    "g4_vis": False,
    "par_energy": 5.0,
    "source": PLACEMENT,
}


def test_experiment_overrides_source_overrides_g4setup() -> None:
    configuration = g4_configuration(SOURCE, G4SETUP, 3, None, 0.1)

    # of the experiment, whatever the files say
    # 3 events to record, generated until there are that many
    assert configuration["recorded_events"] == 3
    assert configuration["total_events"] == GENERATED_LIMIT
    counted = g4_configuration(SOURCE, G4SETUP, None, None, None, generated=5)
    assert (counted["recorded_events"], counted["total_events"]) == (None, 5)
    assert configuration["edep_min"] is None
    assert configuration["edep_max"] == 0.1
    # the particle is of the source
    assert configuration["par_energy"] == 1000.0
    # the surroundings are of the g4setup; the names of the files are gone
    assert configuration["geant4_model"] == "time_resolution"
    assert configuration["object"] == {"elemental": {}}
    assert "name" not in configuration and "kind" not in configuration
    # where the source is and where it aims are of the g4setup
    assert configuration["par_in"] == [0, 0, -1000] and configuration["par_out"] == [0, 0, 1000]
    with pytest.raises(ValueError, match="par_in"):
        g4_configuration({**SOURCE, "par_in": [0, 0, 1000]}, G4SETUP, 1, None, None)
    with pytest.raises(ValueError, match="does not place the source"):
        g4_configuration(
            SOURCE, {k: v for k, v in G4SETUP.items() if k != "source"}, 1, None, None
        )


def test_source_of_an_unknown_kind_is_refused() -> None:
    with pytest.raises(ValueError, match="laser"):
        simulate_deposits(None, {"kind": "laser"}, None, 1, 0)


DEVICE = SimpleNamespace(l_x=100.0, l_y=100.0, l_z=300.0, material="Si")


def test_toy_mip_takes_the_step_limit_of_the_g4setup() -> None:
    device = DEVICE
    source = {"kind": "toy_mip", "landau_sampling": False}

    alone = simulate_deposits(device, source, None, 1, 0)
    coarse = simulate_deposits(device, source, {"maxstep": 50}, 1, 0)

    assert len(alone.events[0].e) == 150
    assert len(coarse.events[0].e) == 6


def test_par_angle_turns_the_source_about_where_it_enters_the_device() -> None:
    # 50 um thick; the source comes up along +z and enters the top face at (0, 0, 0)
    placed = g4_configuration(
        SOURCE, {**G4SETUP, "source": {**PLACEMENT, "angle": 60}}, 1, None, None
    )
    turned = tilted(placed, 50.0)
    assert turned["par_in"] == pytest.approx([-1000 * math.sin(math.radians(60)), 0, -500])
    assert turned["par_out"] == pytest.approx([1000 * math.sin(math.radians(60)), 0, 500])
    assert placed["par_in"] == [0, 0, -1000]
    # a source 0.5 um above the face stays above it at any angle
    close = {"par_in": [0, 0, -0.5], "par_out": [0, 0, 500], "par_angle": 80}
    assert tilted(close, 500.0)["par_in"][2] < 0.0
    with pytest.raises(ValueError, match="neither face"):
        tilted({"par_in": [0, 0, 20], "par_out": [0, 0, 500], "par_angle": 30}, 50.0)


def test_every_particle_takes_from_the_source_what_it_does_not_give() -> None:
    source = {**SOURCE, "particles": [{}, {"offset": [30, 0, 0], "par_energy": 80.0}]}
    first, second = g4_configuration(source, G4SETUP, 1, None, None)["particles"]
    assert first["par_in"] == [0, 0, -1000] and first["par_energy"] == 1000.0
    assert second["par_in"] == [30, 0, -1000] and second["par_energy"] == 80.0
    assert second["par_out"] == [30, 0, 1000] and second["par_type"] == "pi-"
    # par_angle turns the points of the particles with those of the source
    placed = g4_configuration(
        source, {**G4SETUP, "source": {**PLACEMENT, "angle": 90}}, 1, None, None
    )
    assert tilted(placed, 50.0)["particles"][1]["par_in"] == pytest.approx([-1000, 0, -30])


def _box(position_x, side_x):
    return {
        "position_x": position_x, "position_y": 0, "position_z": 0,
        "side_x": side_x, "side_y": 10, "side_z": 10,
    }


def test_world_holds_the_device_the_objects_and_the_source() -> None:
    small = SimpleNamespace(l_x=1300, l_y=1300, l_z=50)
    wide = SimpleNamespace(l_x=96791, l_y=48000, l_z=305)  # ITk-Si-strip

    # what fits stays in the world it always had
    assert world_half_side(small, {**SOURCE, "par_in": [0, 0, 17000], "par_radius": 2500}) == WORLD_HALF_SIDE
    # a device wider than the world: its edge is inside, with room around
    assert world_half_side(wide, SOURCE) == 96791
    # an object and a source that start beyond the world
    assert world_half_side(small, {"object": {"elemental": {"far": _box(29000, 2000)}}}) == 60000
    assert world_half_side(small, {"particles": [{"par_in": [0, -26000, 0]}]}) == 52000
    # a disk of a source reaches by its radius
    assert world_half_side(small, {"par_in": [24000, 0, 0], "par_radius": 2000}) == 52000


def test_generated_fraction_is_the_solid_angle_of_the_cone() -> None:
    sr90 = {"nuclides": [[38, 90]], "par_cone": 15}
    # (1 - cos 15 degrees) / 2 of all directions
    assert generated_fraction(sr90) == pytest.approx(0.017037, rel=1e-4)
    assert generated_fraction({"nuclides": [[38, 90]]}) == 1.0
    assert generated_fraction(SOURCE) == 1.0


def test_an_event_draws_the_same_pairs_whatever_else_is_recorded() -> None:
    from raser.core import seeding

    device = SimpleNamespace(l_x=100.0, l_y=100.0, l_z=300.0, material="Si")
    source = {"kind": "toy_mip", "landau_sampling": True}
    runs = []
    for edep_min in (None, 0.124):  # about half of the tracks lose more
        seeding.seed_generators(4)
        deposits = simulate_deposits(device, source, None, None, 0, edep_min=edep_min, generated=40)
        runs.append({event.event: event.pairs for event in deposits.events})
    everything, some = runs
    # the window drops some tracks; those it keeps drew the same pairs
    assert 0 < len(some) < len(everything)
    assert all(some[number] == everything[number] for number in some)
