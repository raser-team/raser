from types import SimpleNamespace

import numpy as np
import pytest

from raser.core import seeding
from raser.core.deposit.generation import GENERATED_LIMIT
from raser.core.deposit.mip_track import mip_deposits


def _device(material: str) -> SimpleNamespace:
    return SimpleNamespace(l_x=1000.0, l_y=800.0, l_z=300.0, material=material)


def _mip(
    device,
    source,
    events,
    max_step,
    edep_min=None,
    edep_max=None,
    generated=None,
    generated_limit=GENERATED_LIMIT,
):
    """mip_deposits of the one slot "Device"."""
    return mip_deposits(
        {"Device": device},
        None,
        source,
        events,
        max_step,
        {"Device": (edep_min, edep_max)},
        "all",
        None,
        generated,
        generated_limit,
    )


@pytest.mark.parametrize(
    ("material", "energy_per_piece"),
    # 50 um pieces: 80 pairs/um * 3.6 eV and 55 pairs/um * 8.4 eV
    [("Si", 0.0144), ("SiC", 0.0231)],
)
def test_track_without_fluctuation_loses_the_energy_of_the_material(
    material: str, energy_per_piece: float
) -> None:
    deposits = _mip(_device(material), {"landau_sampling": False}, 2, 50.0)

    assert deposits.generated_events == 2
    assert [event.event for event in deposits.events] == [0, 1]
    track = deposits.events[1]
    assert track.e == pytest.approx([energy_per_piece] * 6)
    assert track.z == pytest.approx([25.0, 75.0, 125.0, 175.0, 225.0, 275.0])
    assert track.x == pytest.approx([500.0] * 6)
    assert track.y == pytest.approx([400.0] * 6)
    # each piece runs from its start through its middle: 50 um, one after another
    assert track.z_start == pytest.approx([0.0, 50.0, 100.0, 150.0, 200.0, 250.0])
    assert track.x_start == pytest.approx([500.0] * 6)


def test_energy_window_drops_the_track_and_keeps_the_generated_number() -> None:
    # the track loses 6 * 0.0144 = 0.0864 MeV
    source = {"landau_sampling": False}

    below = _mip(_device("Si"), source, None, 50.0, edep_min=0.09, generated=3)
    above = _mip(_device("Si"), source, None, 50.0, edep_max=0.08, generated=3)
    inside = _mip(_device("Si"), source, 3, 50.0, 0.08, 0.09)

    assert (below.generated_events, len(below.events)) == (3, 0)
    assert (above.generated_events, len(above.events)) == (3, 0)
    assert len(inside.events) == 3


def test_landau_width_scales_with_the_length_of_the_piece() -> None:
    seeding.seed_generators(5)
    source = {"landau_sampling": True, "packets": 20000}

    track = _mip(_device("Si"), source, 1, 50.0).events[0]

    # pieces of 0.015 um; the median of a Landau lies 1.3558 widths above
    # its location, known here to 0.03 widths
    location = 80.0 * 3.6e-6 * 0.015
    width = 2.0e-5 * 0.015
    assert np.median(track.e) == pytest.approx(
        location + 1.3558 * width, abs=0.15 * width
    )


def test_drawn_track_starts_in_the_range_and_is_straight() -> None:
    seeding.seed_generators(5)
    source = {
        "landau_sampling": False,
        "start": [210.0, 270.0, 0.0],
        "end": [210.0, 270.0, 300.0],
        "position_range_um": {"x": [150.0, 270.0], "y": [270.0, 270.0]},
        "direction_sigma_mrad": {"x": 100.0, "y": 0.0},
    }

    tracks = _mip(_device("Si"), source, 50, 50.0).events

    starts = [t.x[0] - (t.x[1] - t.x[0]) / 2 for t in tracks]
    slopes = [(t.x[-1] - t.x[0]) / (t.z[-1] - t.z[0]) for t in tracks]
    assert min(starts) >= 150.0 and max(starts) <= 270.0
    assert np.std(starts) > 20.0  # uniform over 120 um: 34.6
    assert np.std(slopes) == pytest.approx(0.1, rel=0.35)
    assert all(t.y == pytest.approx([270.0] * len(t.y)) for t in tracks)
    for t in tracks:
        assert np.diff(t.x) == pytest.approx([np.diff(t.x)[0]] * (len(t.x) - 1))


def test_key_that_is_not_read_is_refused() -> None:
    source = {"landau_sampling": False, "pairs_per_um": 80.0}

    with pytest.raises(ValueError, match="pairs_per_um"):
        _mip(_device("Si"), source, 1, 50.0)


def test_tracks_are_generated_until_enough_are_recorded() -> None:
    # about half of the tracks lose more than 0.105 MeV
    source = {"landau_sampling": True}
    asked = _mip(_device("Si"), source, 20, 50.0, edep_min=0.105)
    assert len(asked.events) == 20
    assert 20 < asked.generated_events < 200
    # the last generated track is the last recorded one: nothing is thrown away
    assert asked.events[-1].event == asked.generated_events - 1

    counted = _mip(_device("Si"), source, None, 50.0, edep_min=0.105, generated=100)
    assert counted.generated_events == 100
    assert 0 < len(counted.events) < 100

    with pytest.raises(RuntimeError, match="0 of the 1 events"):
        _mip(_device("Si"), source, 1, 50.0, edep_min=100.0, generated_limit=50)
    with pytest.raises(ValueError, match="not both"):
        _mip(_device("Si"), source, 1, 50.0, generated=1)
    # nothing to record, nothing to generate, no room to generate: errors
    for counts in (
        {"events": 0},
        {"events": None, "generated": 0},
        {"events": 1, "generated_limit": 0},
    ):
        with pytest.raises(ValueError, match="at least 1"):
            _mip(_device("Si"), source, max_step=50.0, **counts)


def _column(**slots):
    """A layout of the slots (name -> options) 100 um apart along the beam, each
    100 x 100 x 50 um."""
    from raser.core.deposit.along_beam import parse_along_beam

    devices = {
        name: SimpleNamespace(l_x=100.0, l_y=100.0, l_z=50.0, material="Si")
        for name in slots
    }
    column = ["source"]
    for name, options in slots.items():
        column += [{"gap": 100}, {"slot": name, **options}]
    return devices, parse_along_beam({"object": {}, "along_beam": column}, devices)


def _mip_slots(devices, layout, require, windows=None, source=None, generated=1):
    windows = windows or {name: (None, None) for name in devices}
    source = source or {"landau_sampling": False}
    return mip_deposits(
        devices, layout, source, None, 2.0, windows, require, None, generated=generated
    )


def test_a_track_through_slots_leaves_the_piece_of_each_in_its_own_coordinates() -> (
    None
):
    devices, layout = _column(ref={}, dut={"facing": "downstream"})

    event = _mip_slots(devices, layout, "ref AND dut").events[0]

    ref = [k for k, name in enumerate(event.detector) if name == "ref"]
    dut = [k for k, name in enumerate(event.detector) if name == "dut"]
    # 50 um in each, in pieces of 2 um, 80 pairs/um at 3.6 eV
    assert len(ref) == len(dut) == 25
    assert [event.e[k] for k in ref] == pytest.approx([80 * 3.6e-6 * 2] * 25)
    # the track runs along the axis: the middle of the face, x and y of the device
    assert [event.x[k] for k in ref + dut] == pytest.approx([50.0] * 50)
    assert [event.y[k] for k in ref + dut] == pytest.approx([50.0] * 50)
    # the front face of the upstream device meets the track first; the one of
    # the downstream device is the last it reaches
    assert [event.z[k] for k in ref[:2]] == pytest.approx([1.0, 3.0])
    assert [event.z[k] for k in dut[:2]] == pytest.approx([49.0, 47.0])
    assert [event.z_start[k] for k in dut[:2]] == pytest.approx([50.0, 48.0])
    # the slots follow each other as the devices are given
    assert ref == list(range(25)) and dut == list(range(25, 50))


def test_a_piece_of_the_track_outside_the_device_is_left_out_and_a_miss_is_no_hit() -> (
    None
):
    devices, layout = _column(ref={}, dut={"offset": [200, 0]})

    both = _mip_slots(devices, layout, "ref AND dut")
    anyone = _mip_slots(devices, layout, "any")

    # the second device lies 200 um off the axis: the track misses it
    assert both.events == []
    assert {name for event in anyone.events for name in event.detector} == {"ref"}
    assert len(anyone.events[0].e) == 25


def test_the_energy_window_of_each_slot_counts_only_the_pieces_inside_it() -> None:
    devices, layout = _column(ref={}, dut={})
    # 25 pieces of 5.76e-4 MeV: 0.0144 MeV in each slot
    inside = {"ref": (0.014, 0.015), "dut": (0.014, None)}
    ref_too_low = {"ref": (0.02, None), "dut": (None, None)}

    assert len(_mip_slots(devices, layout, "ref AND dut", inside).events) == 1
    assert _mip_slots(devices, layout, "ref AND dut", ref_too_low).events == []
    # one slot left in the window is enough for "any", and the other keeps its pieces
    kept = _mip_slots(devices, layout, "any", ref_too_low).events[0]
    assert set(kept.detector) == {"ref", "dut"}


def test_a_track_from_the_source_takes_no_start_nor_end() -> None:
    devices, layout = _column(ref={}, dut={})
    for key, value in (
        ("start", [0, 0, 0]),
        ("end", [0, 0, 1]),
        ("position_range_um", {}),
    ):
        with pytest.raises(ValueError, match=key):
            _mip_slots(
                devices, layout, "any", source={"landau_sampling": False, key: value}
            )


def test_the_slope_of_a_track_lengthens_its_piece_and_moves_it_across_the_device() -> (
    None
):
    seeding.seed_generators(3)
    devices, layout = _column(ref={}, dut={})
    source = {"landau_sampling": False, "direction_sigma_mrad": {"x": 100.0, "y": 0.0}}

    events = _mip_slots(devices, layout, "any", source=source, generated=40).events

    assert len(events) == 40
    for event in events:
        ref = [k for k, name in enumerate(event.detector) if name == "ref"]
        slope = (event.x[ref[-1]] - event.x[ref[0]]) / (
            event.z[ref[-1]] - event.z[ref[0]]
        )
        # the energy follows the length along the track, 50 um * sqrt(1 + slope^2)
        length = 50.0 * (1 + slope**2) ** 0.5
        assert sum(event.e[k] for k in ref) == pytest.approx(
            80 * 3.6e-6 * length, rel=1e-9
        )
        # the track leaves the axis in proportion to the distance from the source
        assert event.x[ref[0]] == pytest.approx(
            50 + slope * (100 + 25.0 / len(ref)), abs=1e-6
        )
    assert np.std([e.x[0] for e in events]) > 1.0
