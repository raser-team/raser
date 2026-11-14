from types import SimpleNamespace

import numpy as np
import pytest

from raser.core import seeding
from raser.core.current import drift as drift_module
from raser.core.current.drift import drift
from raser.core.current.drift import induced_charges
from raser.core.current.drift import surviving

MOBILITY = 1000.0  # cm^2/V/s
FIELD = 1.0e4  # V/cm, so carriers move at 1e7 cm/s = 100 um/ns


class _Field:
    """FIELD along z above z = 10 um, none below; no doping."""

    def get_e_field_cached(self, x, y, z):
        return (0.0, 0.0, FIELD if z >= 10.0 else 0.0)

    def get_doping_cached(self, x, y, z):
        return 0.0

    def get_w_p_cached(self, x, y, z, electrode):
        # two electrodes facing each other at z = 0 and z = 50 um
        return 1.0 - z / 50.0 if electrode == 0 else z / 50.0


def _device():
    return SimpleNamespace(l_x=100.0, l_y=100.0, l_z=50.0, temperature=300.0)


def _mobility(temperature, doping, charge, field):
    return MOBILITY


def _um_ps(point):
    """x, y, z [um] and t [ps] of a point of a path, so that t is not below the tolerance."""
    return [point[0], point[1], point[2], point[3] * 1.0e12]


def test_hole_drifts_along_the_field_and_stops_on_the_surface() -> None:
    # 100 um/ns from z = 25 um: the surface at 50 um is reached after 250 ps
    path, reason = drift(
        50.0, 50.0, 25.0, 1.0e-9, 100.0, _device(), _Field(), _mobility, 3.0e-11, diffusion=False
    )

    assert reason == "left_device"
    assert _um_ps(path[1]) == pytest.approx([50.0, 50.0, 28.0, 1030.0])
    assert _um_ps(path[-1]) == pytest.approx([50.0, 50.0, 50.0, 1250.0])
    assert len(path) == 10


def test_electron_drifts_against_the_field_and_stops_where_it_is_low() -> None:
    # 100 um/ns from z = 25 um: 15 um to the field-free layer below 10 um
    path, reason = drift(
        50.0, 50.0, 25.0, 0.0, -100.0, _device(), _Field(), _mobility, 3.0e-11, diffusion=False
    )

    assert reason == "low_field"
    assert _um_ps(path[1]) == pytest.approx([50.0, 50.0, 22.0, 30.0])
    assert _um_ps(path[-1]) == pytest.approx([50.0, 50.0, 7.0, 180.0])


def test_diffusion_spreads_a_carrier_by_2_d_t_on_each_axis() -> None:
    # D = mobility kT/e = 1000 * 0.025852 cm^2/s; over 100 steps of 1 ps
    # the variance on x is 2 D t = 5.1704e-9 cm^2 = 0.51704 um^2
    seeding.seed_generators(3)
    ends = []
    for _ in range(600):
        path, _ = drift(50.0, 50.0, 30.0, 0.0, 1.0, _device(), _Field(), _mobility, 1.0e-12)
        ends.append(path[100])

    x = np.array(ends)[:, 0]
    assert np.array(ends)[:, 3] * 1.0e12 == pytest.approx(100.0)
    assert x.mean() == pytest.approx(50.0, abs=0.1)
    assert x.var() == pytest.approx(0.51704, rel=0.15)


def test_drift_without_diffusion_does_not_ask_the_random_stream(monkeypatch) -> None:
    def no_stream(name):
        raise AssertionError("the random stream was asked")

    monkeypatch.setattr(drift_module, "stream", no_stream)

    path, _ = drift(
        50.0, 50.0, 25.0, 0.0, 100.0, _device(), _Field(), _mobility, 3.0e-11, diffusion=False
    )

    assert set(path[:, 0]) == {50.0}


class _Junction(_Field):
    """Below z = 10 um the field is low_field and the doping is doping."""

    def __init__(self, doping, low_field=100.0):
        self.doping = doping
        self.low_field = low_field

    def get_e_field_cached(self, x, y, z):
        return (0.0, 0.0, FIELD if z >= 10.0 else self.low_field)

    def get_doping_cached(self, x, y, z):
        return self.doping if z < 10.0 else 0.0


def test_electron_is_collected_where_resistivity_and_field_are_low() -> None:
    # 1e19 cm^-3 at 1000 cm^2/V/s is 6.2e-4 ohm cm
    path, reason = drift(
        50.0, 50.0, 25.0, 0.0, -100.0, _device(), _Junction(1.0e19), _mobility, 3.0e-11,
        diffusion=False,
    )

    assert reason == "collected"
    assert _um_ps(path[-1]) == pytest.approx([50.0, 50.0, 7.0, 180.0])


def test_electron_drifts_on_through_a_low_field_of_high_resistivity() -> None:
    # 1e12 cm^-3 at 1000 cm^2/V/s is 6.2e3 ohm cm; 100 V/cm moves it 1 um/ns
    path, reason = drift(
        50.0, 50.0, 25.0, 0.0, -100.0, _device(), _Junction(1.0e12), _mobility, 3.0e-11,
        diffusion=False,
    )

    assert reason == "left_device"
    assert _um_ps(path[-1]) == pytest.approx([50.0, 50.0, 0.0, 7180.0])


def test_electron_drifts_on_through_a_high_field_of_low_resistivity() -> None:
    # a gain layer: doped to low resistivity but depleted, the field stays high
    path, reason = drift(
        50.0, 50.0, 25.0, 0.0, -100.0, _device(), _Junction(1.0e19, FIELD), _mobility, 3.0e-11,
        diffusion=False,
    )

    assert reason == "left_device"
    assert _um_ps(path[-1]) == pytest.approx([50.0, 50.0, 0.0, 250.0])


def test_a_pair_collected_between_two_electrodes_induces_its_charge_on_each() -> None:
    # hole from z = 25 to the electrode at 50 um, electron to the low field below 10 um
    hole, _ = drift(
        50.0, 50.0, 25.0, 0.0, 100.0, _device(), _Field(), _mobility, 3.0e-11, diffusion=False
    )
    electron, _ = drift(
        50.0, 50.0, 25.0, 0.0, -100.0, _device(), _Field(), _mobility, 3.0e-11, diffusion=False
    )
    e0 = 1.60217733e-19  # the charges are compared in units of it

    on_front = induced_charges(hole, 100.0, _Field(), 0) / e0
    assert on_front[0] == pytest.approx(100.0 * -3.0 / 50.0)
    assert on_front.sum() == pytest.approx(100.0 * -0.5)
    assert induced_charges(hole, 100.0, _Field(), 1).sum() / e0 == pytest.approx(100.0 * 0.5)
    # the electron stops at z = 7 um, where the weighting potential is 0.86
    assert induced_charges(electron, -100.0, _Field(), 0).sum() / e0 == pytest.approx(
        -100.0 * (0.86 - 0.5)
    )


class _Strips(_Field):
    """Strips 30 um apart along x; the field holds the one centred at x = 50 um.

    Its weighting potential falls linearly in depth under the strip, 20 um
    wide, and is zero beside it.
    """

    def get_w_p_cached(self, x, y, z, electrode):
        return 1.0 - z / 50.0 if abs(x - 50.0) < 10.0 else 0.0


def test_a_hole_under_the_next_strip_induces_on_that_strip_not_on_the_one_of_the_field() -> None:
    hole, _ = drift(
        80.0, 50.0, 25.0, 0.0, 100.0, _device(), _Strips(), _mobility, 3.0e-11, diffusion=False
    )
    e0 = 1.60217733e-19  # the charges are compared in units of it

    assert induced_charges(hole, 100.0, _Strips(), 0).sum() / e0 == pytest.approx(0.0)
    assert induced_charges(hole, 100.0, _Strips(), 0, offset=(30.0, 0.0)).sum() / e0 == (
        pytest.approx(100.0 * -0.5)
    )
    assert induced_charges(hole, 100.0, _Strips(), 0, offset=(-30.0, 0.0)).sum() / e0 == (
        pytest.approx(0.0)
    )


class _Irradiated(_Field):
    """Holes are trapped at 2e9 /s, electrons at 5e9 /s."""

    def get_trap_h_cached(self, x, y, z):
        return 2.0e9

    def get_trap_e_cached(self, x, y, z):
        return 5.0e9


def test_trapping_leaves_the_exponential_of_rate_times_time() -> None:
    # steps of 30 ps: the middles of the first and the sixth are at 15 and 165 ps
    hole, _ = drift(
        50.0, 50.0, 25.0, 1.0e-9, 100.0, _device(), _Field(), _mobility, 3.0e-11, diffusion=False
    )
    electron, _ = drift(
        50.0, 50.0, 25.0, 1.0e-9, -100.0, _device(), _Field(), _mobility, 3.0e-11, diffusion=False
    )

    holes = surviving(hole, 100.0, _Irradiated())
    electrons = surviving(electron, -100.0, _Irradiated())

    assert len(holes) == len(hole) - 1
    assert holes[0] == pytest.approx(100.0 * np.exp(-2.0e9 * 15.0e-12))
    assert holes[5] == pytest.approx(100.0 * np.exp(-2.0e9 * 165.0e-12))
    assert electrons[5] == pytest.approx(-100.0 * np.exp(-5.0e9 * 165.0e-12))
    # the last step of the hole ends on the surface after 10 of the 30 ps
    assert holes[-1] == pytest.approx(100.0 * np.exp(-2.0e9 * 245.0e-12))

