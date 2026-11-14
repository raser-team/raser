from types import SimpleNamespace

import numpy as np
import pytest

from raser.core import seeding
from raser.core.current import drift as drift_module
from raser.core.current.drift import drift

MOBILITY = 1000.0  # cm^2/V/s
FIELD = 1.0e4  # V/cm, so carriers move at 1e7 cm/s = 100 um/ns


class _Field:
    """FIELD along z above z = 10 um, none below; no doping."""

    def get_e_field_cached(self, x, y, z):
        return (0.0, 0.0, FIELD if z >= 10.0 else 0.0)

    def get_doping_cached(self, x, y, z):
        return 0.0


def _device():
    return SimpleNamespace(l_x=100.0, l_y=100.0, l_z=50.0, temperature=300.0)


def _mobility(temperature, doping, charge, field):
    return MOBILITY


def test_hole_drifts_along_the_field_and_stops_on_the_surface() -> None:
    # 100 um/ns from z = 25 um: the surface at 50 um is reached after 250 ps
    path, reason = drift(
        50.0, 50.0, 25.0, 1.0e-9, 100.0, _device(), _Field(), _mobility, 3.0e-11, diffusion=False
    )

    assert reason == "left_device"
    assert path[1] == pytest.approx([50.0, 50.0, 28.0, 1.03e-9])
    assert path[-1] == pytest.approx([50.0, 50.0, 50.0, 1.25e-9])
    assert len(path) == 10


def test_electron_drifts_against_the_field_and_stops_where_it_is_low() -> None:
    # 100 um/ns from z = 25 um: 15 um to the field-free layer below 10 um
    path, reason = drift(
        50.0, 50.0, 25.0, 0.0, -100.0, _device(), _Field(), _mobility, 3.0e-11, diffusion=False
    )

    assert reason == "low_field"
    assert path[1] == pytest.approx([50.0, 50.0, 22.0, 3.0e-11])
    assert path[-1] == pytest.approx([50.0, 50.0, 7.0, 1.8e-10])


def test_diffusion_spreads_a_carrier_by_2_d_t_on_each_axis() -> None:
    # D = mobility kT/e = 1000 * 0.025852 cm^2/s; over 100 steps of 1 ps
    # the variance on x is 2 D t = 5.1704e-9 cm^2 = 0.51704 um^2
    seeding.seed_generators(3)
    ends = []
    for _ in range(600):
        path, _ = drift(50.0, 50.0, 30.0, 0.0, 1.0, _device(), _Field(), _mobility, 1.0e-12)
        ends.append(path[100])

    x = np.array(ends)[:, 0]
    assert np.array(ends)[:, 3] == pytest.approx(1.0e-10)
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
