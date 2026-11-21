from __future__ import annotations

import pytest
from scipy.interpolate import interp1d

from raser.core.field.gradient import STEP
from raser.core.field.gradient import gradient

DEPTH = 50.0e-4  # cm


def _potential(z: float) -> float:
    """A depleted pad: the field falls linearly from 4e4 V/cm at z = 0 to
    2e4 V/cm at the far end. Known only inside the mesh, as a solved field is."""
    inside = interp1d([0.0, DEPTH], [0.0, 0.0])  # raises outside the mesh
    return float(inside(z)) - 4.0e4 * z + 2.0e4 * z * z / DEPTH


@pytest.mark.parametrize(
    "z", [0.0, STEP / 4, STEP / 2, DEPTH / 2, DEPTH - STEP / 4, DEPTH]
)
def test_the_field_is_found_everywhere_in_the_mesh_its_ends_included(z: float) -> None:
    (slope,) = gradient(_potential, [z], [(0.0, DEPTH)])

    field = 4.0e4 - 4.0e4 * z / DEPTH
    assert -slope == pytest.approx(field, abs=4.0e4 * STEP / DEPTH)


def test_each_coordinate_keeps_to_its_own_ends() -> None:
    def potential(z: float, x: float) -> float:
        assert 0.0 <= z <= 1.0 and 2.0 <= x <= 3.0
        return 5.0 * z - 7.0 * x

    assert gradient(potential, [1.0, 2.0], [(0.0, 1.0), (2.0, 3.0)]) == pytest.approx(
        (5.0, -7.0)
    )


@pytest.mark.parametrize("z", [-STEP / 4, DEPTH + STEP / 4])
def test_a_point_outside_the_mesh_has_no_field(z: float) -> None:
    with pytest.raises(ValueError, match="outside the mesh"):
        gradient(lambda z: 0.0, [z], [(0.0, DEPTH)])
