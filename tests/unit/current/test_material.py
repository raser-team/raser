import math

import pytest

from raser.core.current.model import Material


def test_silicon_defaults_are_configured():
    material = Material("Si")

    assert material.permittivity == 11.5
    assert material.mobility_model == "Selberherr"
    assert material.avalanche_model == "vanOverstraeten"


def test_silicon_carbide_defaults_are_configured():
    material = Material("SiC")

    assert material.permittivity == 9.76
    assert material.mobility_model == "Das"
    assert material.avalanche_model == "Hatakeyama"


def test_representative_mobility_values_are_positive_and_finite():
    silicon = Material("Si")
    silicon_carbide = Material("SiC")

    values = [
        silicon.cal_mobility(
            temperature=300, input_doping=1e12, charge=-1, electric_field=1e4
        ),
        silicon.cal_mobility(
            temperature=300, input_doping=1e12, charge=1, electric_field=1e4
        ),
        silicon_carbide.cal_mobility(
            temperature=300, input_doping=1e12, charge=-1, electric_field=1e4
        ),
        silicon_carbide.cal_mobility(
            temperature=300, input_doping=1e12, charge=1, electric_field=1e4
        ),
    ]

    assert all(math.isfinite(value) and value > 0 for value in values)


def test_silicon_mobility_changes_with_charge_type():
    material = Material("Si")

    electron = material.cal_mobility(
        temperature=300,
        input_doping=1e12,
        charge=-1,
        electric_field=1e3,
    )
    hole = material.cal_mobility(
        temperature=300,
        input_doping=1e12,
        charge=1,
        electric_field=1e3,
    )

    assert electron > hole
    assert electron == pytest.approx(1401.573, rel=1e-3)
    assert hole == pytest.approx(434.882, rel=1e-3)


def test_avalanche_coefficient_is_zero_below_model_threshold():
    material = Material("Si")

    assert material.cal_coefficient(1e5, -1, 300) == 0.0


def test_avalanche_coefficient_uses_charge_specific_parameters():
    material = Material("Si")

    electron = material.cal_coefficient(3e5, -1, 300)
    hole = material.cal_coefficient(3e5, 1, 300)

    assert electron > 0
    assert hole > 0
    assert electron != pytest.approx(hole)


def test_avalanche_coefficient_rejects_unknown_model():
    material = Material("Si", avalanche_model="unknown")

    with pytest.raises(ValueError, match="Unsupported avalanche model"):
        material.cal_coefficient(3e5, -1, 300)
