from types import SimpleNamespace

import pytest

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
    path, reason = drift(50.0, 50.0, 25.0, 1.0e-9, 100.0, _device(), _Field(), _mobility, 3.0e-11)

    assert reason == "left_device"
    assert path[1] == pytest.approx([50.0, 50.0, 28.0, 1.03e-9])
    assert path[-1] == pytest.approx([50.0, 50.0, 50.0, 1.25e-9])
    assert len(path) == 10


def test_electron_drifts_against_the_field_and_stops_where_it_is_low() -> None:
    # 100 um/ns from z = 25 um: 15 um to the field-free layer below 10 um
    path, reason = drift(50.0, 50.0, 25.0, 0.0, -100.0, _device(), _Field(), _mobility, 3.0e-11)

    assert reason == "low_field"
    assert path[1] == pytest.approx([50.0, 50.0, 22.0, 3.0e-11])
    assert path[-1] == pytest.approx([50.0, 50.0, 7.0, 1.8e-10])
