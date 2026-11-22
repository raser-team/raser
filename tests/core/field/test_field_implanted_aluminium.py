import pytest

from raser.core.field import implanted_aluminium


def test_sheet_resistance_of_the_layers_spera_et_al_measured():
    # arXiv:2001.08021, tables 1 and 2: 1e20 cm^-3 of aluminium in 300 nm,
    # annealed at 1675, 1775 and 1825 C, 12000, 9750 and 7470 Ohm a square at
    # room temperature. The model takes the mean of their donors and of their
    # mobilities, so each layer is met within a quarter
    dose_cm2 = 1e20 * 300e-7
    resistances = [
        implanted_aluminium.sheet_resistance(dose_cm2, 300e-7, anneal_c, 300.0)
        for anneal_c in (1675.0, 1775.0, 1825.0)
    ]

    for model, measured in zip(resistances, (12000.0, 9750.0, 7470.0)):
        assert model == pytest.approx(measured, rel=0.25)
    # a hotter anneal frees more of the aluminium
    assert resistances[0] > resistances[1] > resistances[2]


def test_cold_layer_holds_more_of_its_holes_on_the_acceptors():
    dose_cm2 = 1e20 * 300e-7
    cold = implanted_aluminium.sheet_resistance(dose_cm2, 300e-7, 1775.0, 250.0)
    warm = implanted_aluminium.sheet_resistance(dose_cm2, 300e-7, 1775.0, 300.0)

    assert implanted_aluminium.holes(4.84e19, 3.49e18, 250.0) < (
        implanted_aluminium.holes(4.84e19, 3.49e18, 300.0)
    )
    assert cold > warm
