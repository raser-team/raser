from types import SimpleNamespace

import numpy as np
import pytest

from raser.core import seeding
from raser.core.interaction.mip_track import mip_deposits


def _device(material: str) -> SimpleNamespace:
    return SimpleNamespace(l_x=1000.0, l_y=800.0, l_z=300.0, material=material)


@pytest.mark.parametrize(
    ("material", "energy_per_piece"),
    # 50 um pieces: 80 pairs/um * 3.6 eV and 55 pairs/um * 8.4 eV
    [("Si", 0.0144), ("SiC", 0.0231)],
)
def test_track_without_fluctuation_loses_the_energy_of_the_material(
    material: str, energy_per_piece: float
) -> None:
    deposits = mip_deposits(_device(material), {"landau_sampling": False}, 2, 50.0)

    assert deposits.generated_events == 2
    assert [event.event for event in deposits.events] == [0, 1]
    track = deposits.events[1]
    assert track.e == pytest.approx([energy_per_piece] * 6)
    assert track.z == pytest.approx([25.0, 75.0, 125.0, 175.0, 225.0, 275.0])
    assert track.x == pytest.approx([500.0] * 6)
    assert track.y == pytest.approx([400.0] * 6)


def test_energy_window_drops_the_track_and_keeps_the_generated_number() -> None:
    # the track loses 6 * 0.0144 = 0.0864 MeV
    source = {"landau_sampling": False}

    below = mip_deposits(_device("Si"), source, 3, 50.0, edep_min=0.09)
    above = mip_deposits(_device("Si"), source, 3, 50.0, edep_max=0.08)
    inside = mip_deposits(_device("Si"), source, 3, 50.0, 0.08, 0.09)

    assert (below.generated_events, len(below.events)) == (3, 0)
    assert (above.generated_events, len(above.events)) == (3, 0)
    assert len(inside.events) == 3


def test_landau_width_scales_with_the_length_of_the_piece() -> None:
    seeding.seed_generators(5)
    source = {"landau_sampling": True, "packets": 20000}

    track = mip_deposits(_device("Si"), source, 1, 50.0).events[0]

    # pieces of 0.015 um; the median of a Landau lies 1.3558 widths above
    # its location, known here to 0.03 widths
    location = 80.0 * 3.6e-6 * 0.015
    width = 2.0e-5 * 0.015
    assert np.median(track.e) == pytest.approx(location + 1.3558 * width, abs=0.15 * width)


def test_drawn_track_starts_in_the_range_and_is_straight() -> None:
    seeding.seed_generators(5)
    source = {
        "landau_sampling": False,
        "start": [210.0, 270.0, 0.0],
        "end": [210.0, 270.0, 300.0],
        "position_range_um": {"x": [150.0, 270.0], "y": [270.0, 270.0]},
        "direction_sigma_mrad": {"x": 100.0, "y": 0.0},
    }

    tracks = mip_deposits(_device("Si"), source, 50, 50.0).events

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
        mip_deposits(_device("Si"), source, 1, 50.0)
