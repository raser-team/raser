import pytest

from raser.core.model.material import Material


@pytest.mark.parametrize(("charge", "low_field"), [(+1, 2064.0), (-1, 1714.0)])
def test_diamond_mobility_at_low_field_is_the_fitted_low_field_mobility(
    charge: int, low_field: float
) -> None:
    mobility = Material("Diamond").cal_mobility(300.0, 0.0, charge, 1.0)

    assert mobility == pytest.approx(low_field, rel=1e-3)


@pytest.mark.parametrize(("charge", "measured"), [(+1, 7.5e6), (-1, 5.6e6)])
def test_diamond_drift_velocity_matches_the_measurement_at_0p8_v_per_um(
    charge: int, measured: float
) -> None:
    # Pernegger et al., J. Appl. Phys. 97 (2005) 073704, section IV: the drift
    # velocities measured at 0.8 V/um, in cm/s.
    field = 8.0e3
    velocity = Material("Diamond").cal_mobility(300.0, 0.0, charge, field) * field

    assert velocity == pytest.approx(measured, rel=2e-2)
