import pytest

from raser.core.current.model import Material


@pytest.mark.parametrize(("charge", "low_field"), [(+1, 1250.0), (-1, 1900.0)])
def test_diamond_mobility_at_low_field_is_lattice_plus_minimum(
    charge: int, low_field: float
) -> None:
    # Undoped diamond at 300 K: mu = mu_min + mu_L (holes 50 + 1200, electrons 100 + 1800).
    mobility = Material("Diamond").cal_mobility(300.0, 0.0, charge, 1.0)

    assert mobility == pytest.approx(low_field, rel=1e-3)


@pytest.mark.parametrize(
    ("charge", "v_sat", "fraction"), [(+1, 1.0e7, 1.0), (-1, 2.7e7, 0.986)]
)
def test_diamond_drift_velocity_saturates_at_high_field(
    charge: int, v_sat: float, fraction: float
) -> None:
    # At 1 MV/cm mu E / v_sat is 125 for holes (beta 1.5) and 70 for electrons
    # (beta 1): the velocity is v_sat, and 70/71 of it.
    field = 1.0e6
    velocity = Material("Diamond").cal_mobility(300.0, 0.0, charge, field) * field

    assert velocity == pytest.approx(fraction * v_sat, rel=5e-3)
