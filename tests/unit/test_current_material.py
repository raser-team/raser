import math

from raser.current.model import Material


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
