from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from raser.core.current.model import Material
from raser.core.field.devsim_field import DevsimField

DEVICE = SimpleNamespace(
    material="Si",
    avalanche_model="vanOverstraeten",
    temperature=300.0,
    l_x=100.0,
    l_y=100.0,
)


def _field(nodes_um: list[float], fields_v_per_cm: list[float]) -> DevsimField:
    """A one-dimensional field with these mesh nodes and one field in each
    interval between them, positive along the depth."""
    nodes = np.array(nodes_um) * 1e-4  # cm
    potential = np.concatenate(
        [[0.0], -np.cumsum(np.array(fields_v_per_cm) * np.diff(nodes))]
    )
    field = object.__new__(DevsimField)
    field.name, field.voltage, field.axes = "device", 100.0, ("z",)
    field.potential_points = nodes.reshape(-1, 1)
    field.get_potential = lambda x, y, z: float(np.interp(z * 1e-4, nodes, potential))
    return field


def _closed_form(field_v_per_cm: float, layer_um: float) -> float:
    """Gain minus one of a layer with one field, electrons multiplying."""
    coefficient = Material("Si", avalanche_model="vanOverstraeten").cal_coefficient
    electrons = coefficient(abs(field_v_per_cm), -1, 300.0)
    holes = coefficient(abs(field_v_per_cm), +1, 300.0)
    if field_v_per_cm < 0:  # holes multiply
        electrons, holes = holes, electrons
    growth = np.exp((electrons - holes) * layer_um * 1e-4)
    feedback = holes / (electrons - holes) * (growth - 1)
    return growth / (1 - feedback) - 1


def test_a_uniform_layer_has_the_closed_form_gain_whatever_its_nodes() -> None:
    expected = _closed_form(3.0e5, 1.0)

    assert expected > 0.1
    assert _field([0.0, 1.0], [3.0e5]).planar_gain(DEVICE) == pytest.approx(
        expected, rel=1e-9
    )
    uneven = _field([0.0, 0.03, 0.5, 0.55, 1.0], [3.0e5] * 4)
    assert uneven.planar_gain(DEVICE) == pytest.approx(expected, rel=1e-9)


def test_a_thin_gain_layer_inside_a_thick_bulk_gives_the_gain_of_the_layer() -> None:
    # 1 um at 3e5 V/cm between coarse intervals at 1e4 V/cm, where nothing multiplies
    field = _field([0.0, 1.0, 2.0, 50.0], [1.0e4, 3.0e5, 1.0e4])

    assert field.planar_gain(DEVICE) == pytest.approx(
        _closed_form(3.0e5, 1.0), rel=1e-6
    )


def test_the_multiplied_carriers_start_in_the_middle_of_the_strongest_field() -> None:
    field = _field([0.0, 1.0, 2.0, 50.0], [1.0e4, 3.0e5, 1.0e4])

    assert field.planar_gain_depth(DEVICE) == pytest.approx(1.5)


def test_the_carrier_that_multiplies_is_judged_where_the_field_is_strongest() -> None:
    # a weak field against the depth in front of the layer does not make the holes multiply
    field = _field([0.0, 1.0, 2.0, 50.0], [-1.0e4, 3.0e5, 1.0e4])

    assert field.planar_gain(DEVICE) == pytest.approx(
        _closed_form(3.0e5, 1.0), rel=1e-6
    )


def test_a_field_against_the_depth_lets_the_holes_multiply() -> None:
    field = _field([0.0, 1.0], [-3.0e5])

    assert field.planar_gain(DEVICE) == pytest.approx(
        _closed_form(-3.0e5, 1.0), rel=1e-9
    )
    assert _closed_form(-3.0e5, 1.0) != pytest.approx(
        _closed_form(3.0e5, 1.0), rel=0.05
    )


def test_a_device_and_its_mirror_image_have_the_same_gain() -> None:
    # the layer is not uniform, so the gain depends on which way it is crossed
    front = _field([0.0, 1.0, 2.0, 50.0], [2.5e5, 3.0e5, 1.0e4])
    back = _field([0.0, 48.0, 49.0, 50.0], [-1.0e4, -3.0e5, -2.5e5])
    crossed_the_other_way = _field([0.0, 1.0, 2.0, 50.0], [3.0e5, 2.5e5, 1.0e4])

    assert back.planar_gain(DEVICE) == pytest.approx(front.planar_gain(DEVICE), rel=1e-9)
    assert back.planar_gain_carrier(DEVICE) == front.planar_gain_carrier(DEVICE) == -1
    assert crossed_the_other_way.planar_gain(DEVICE) != pytest.approx(
        front.planar_gain(DEVICE), rel=0.01
    )


def test_a_layer_at_the_back_multiplies_the_carriers_that_drift_to_the_back() -> None:
    # the field is along the depth: holes drift to the back, through the layer
    field = _field([0.0, 48.0, 49.0, 50.0], [1.0e4, 1.0e4, 3.0e5])

    assert field.planar_gain_carrier(DEVICE) == +1
    assert field.planar_gain(DEVICE) == pytest.approx(_closed_form(-3.0e5, 1.0), rel=1e-6)


def test_a_pair_made_in_front_of_the_layer_has_the_gain_of_the_other_carrier() -> None:
    # the field is along the depth: behind the layer the electrons drift through it,
    # in front of it the holes do
    field = _field([0.0, 1.0, 2.0, 50.0], [1.0e4, 3.0e5, 1.0e4])
    electrons, holes = _closed_form(3.0e5, 1.0), _closed_form(-3.0e5, 1.0)

    assert field.planar_gain_at(DEVICE, 25.0) == pytest.approx(electrons, rel=1e-6)
    assert field.planar_gain_at(DEVICE, 0.5) == pytest.approx(holes, rel=1e-6)
    assert holes < 0.5 * electrons
    assert holes < field.planar_gain_at(DEVICE, 1.5) < electrons


def test_a_layer_beyond_breakdown_is_refused() -> None:
    with pytest.raises(ValueError, match="breaks down at 100.0 V"):
        _field([0.0, 3.0], [5.0e5]).planar_gain(DEVICE)


def test_the_gain_is_integrated_once() -> None:
    field = _field([0.0, 1.0], [3.0e5])
    first = field.planar_gain(DEVICE)
    field.get_potential = None  # a second integration would fail

    assert field.planar_gain(DEVICE) == first
