from __future__ import annotations

import math

import pytest

from raser.core.field import physics_irradiation

K_T = 0.025852 * 1.6e-19  # J, 300 K
SILICON = {
    "N_c": 2.82e19,
    "N_v": 1.83e19,
    "E_g": 1.12 * 1.6e-19,
    "k_T": K_T,
    "vel_mean": 1e7,
}
SIGMA_N, SIGMA_P, DENSITY = 2.0e-14, 5.0e-15, 1.0e14  # cm^2, cm^2, defects per cm^3


def _models(
    monkeypatch: pytest.MonkeyPatch,
    level_ev: float,
    electrons: float,
    holes: float,
    kind: str | None = "acceptor",
) -> dict[str, float]:
    """The values of the node models that CreateIrradiation hands devsim for
    one defect `level_ev` above the middle of the gap, at these carrier densities."""
    parameters = dict(SILICON)
    models = {}
    monkeypatch.setattr(
        physics_irradiation.devsim,
        "set_parameter",
        lambda device, region, name, value: parameters.update({name: value}),
    )
    monkeypatch.setattr(
        physics_irradiation,
        "CreateNodeModel",
        lambda device, region, name, expression: models.update({name: expression}),
    )
    monkeypatch.setattr(
        physics_irradiation, "CreateNodeModelDerivative", lambda *given: None
    )
    defect = {
        "name": "one",
        "E_t_ev": level_ev,
        "g_int": DENSITY,
        "sigma_n_irr": SIGMA_N,
        "sigma_p_irr": SIGMA_P,
    }
    if kind is not None:
        defect["type"] = kind
    physics_irradiation.CreateIrradiation(
        "device", "region", label="custom", flux=1.0, custom_defect=[defect]
    )
    values = {**parameters, "Electrons": electrons, "Holes": holes, "exp": math.exp}
    return {
        name: eval(expression, {}, values)
        for name, expression in models.items()
        if name != "U_r"
    }


def _trapping_rates(
    monkeypatch: pytest.MonkeyPatch, level_ev: float, electrons: float, holes: float
) -> tuple[float, float]:
    """The electron and the hole trapping rate in 1/s."""
    models = _models(monkeypatch, level_ev, electrons, holes)
    return models["TrappingRate_n"], models["TrappingRate_p"]


def _charge(
    monkeypatch: pytest.MonkeyPatch, level_ev: float, kind: str, electrons: float = 0.0
) -> float:
    """The charge of the defects in elementary charges per cm^3."""
    models = _models(monkeypatch, level_ev, electrons, 0.0, kind)
    return models["TrappedHoles"] - models["TrappedElectrons"]


def test_a_depleted_defect_above_midgap_is_empty_and_traps_electrons(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    electron_rate, hole_rate = _trapping_rates(
        monkeypatch, 0.46, electrons=0.0, holes=0.0
    )

    assert electron_rate == pytest.approx(1e7 * SIGMA_N * DENSITY)
    assert hole_rate < 1e-10 * 1e7 * SIGMA_P * DENSITY


def test_a_depleted_defect_below_midgap_is_filled_and_traps_holes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    electron_rate, hole_rate = _trapping_rates(
        monkeypatch, -0.46, electrons=0.0, holes=0.0
    )

    assert hole_rate == pytest.approx(1e7 * SIGMA_P * DENSITY)
    assert electron_rate < 1e-10 * 1e7 * SIGMA_N * DENSITY


def test_a_defect_among_many_electrons_is_filled_and_traps_only_holes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    electron_rate, hole_rate = _trapping_rates(
        monkeypatch, 0.2, electrons=1e19, holes=0.0
    )

    assert hole_rate == pytest.approx(1e7 * SIGMA_P * DENSITY, rel=1e-3)
    assert electron_rate < 1e-3 * 1e7 * SIGMA_N * DENSITY


def test_a_depleted_donor_is_positive_while_empty_and_an_acceptor_negative_while_filled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # above midgap a depleted defect is empty, below it is filled
    assert _charge(monkeypatch, 0.46, "donor") == pytest.approx(DENSITY)
    assert abs(_charge(monkeypatch, 0.46, "acceptor")) < 1e-10 * DENSITY
    assert _charge(monkeypatch, -0.46, "acceptor") == pytest.approx(-DENSITY)
    assert abs(_charge(monkeypatch, -0.46, "donor")) < 1e-10 * DENSITY


def test_a_donor_among_many_electrons_is_filled_and_neutral(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert abs(_charge(monkeypatch, 0.2, "donor", electrons=1e19)) < 1e-3 * DENSITY


def test_a_defect_that_is_neither_donor_nor_acceptor_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(ValueError, match="one must have .type."):
        _models(monkeypatch, 0.46, 0.0, 0.0, kind=None)
