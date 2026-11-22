from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from raser.core.field import physics_irradiation


def _written_parameters(monkeypatch: pytest.MonkeyPatch, material: str, flux: float) -> dict[str, Any]:
    parameters: dict[str, Any] = {}
    devsim = SimpleNamespace(
        set_parameter=lambda device, region, name, value: parameters.__setitem__(name, value),
        get_material=lambda device, region: material,
    )
    monkeypatch.setattr(physics_irradiation, "devsim", devsim)
    monkeypatch.setattr(physics_irradiation, "CreateNodeModel", lambda *args: None)
    monkeypatch.setattr(physics_irradiation, "CreateNodeModelDerivative", lambda *args: None)
    physics_irradiation.CreateIrradiation("d", "r", label="CommonDefect", flux=flux)
    return parameters


def test_diamond_carries_its_background_defects_without_any_flux(monkeypatch: pytest.MonkeyPatch) -> None:
    parameters = _written_parameters(monkeypatch, "Diamond", 0.0)

    assert parameters["N_t_irr_BoronAcceptor"] == 2.0e14
    assert parameters["N_t_irr_SubstitutionalNitrogen_P1"] == 5.0e14
    assert parameters["N_t_irr_VacancyRelated"] == 1.0e14


@pytest.mark.parametrize(("flux", "expected"), [(0.0, 0.0), (1e14, 1e14)])
def test_silicon_carbide_keeps_its_defects_proportional_to_flux(
    monkeypatch: pytest.MonkeyPatch, flux: float, expected: float
) -> None:
    parameters = _written_parameters(monkeypatch, "SiliconCarbide", flux)

    assert {name for name in parameters if name.startswith("N_t_irr_")} == {"N_t_irr_Z12", "N_t_irr_EH67"}
    assert parameters["N_t_irr_Z12"] == expected
    assert parameters["N_t_irr_EH67"] == expected


def _written_models(monkeypatch: pytest.MonkeyPatch, material: str) -> dict[str, str]:
    models: dict[str, str] = {}
    devsim = SimpleNamespace(
        set_parameter=lambda device, region, name, value: None,
        get_material=lambda device, region: material,
    )
    monkeypatch.setattr(physics_irradiation, "devsim", devsim)
    monkeypatch.setattr(physics_irradiation, "CreateNodeModel", lambda device, region, name, expression: models.__setitem__(name, expression))
    monkeypatch.setattr(physics_irradiation, "CreateNodeModelDerivative", lambda *args: None)
    physics_irradiation.CreateIrradiation("d", "r", label="CommonDefect", flux=0.0)
    return models


def test_diamond_holds_the_densities_in_its_defect_terms_at_the_floor(monkeypatch: pytest.MonkeyPatch) -> None:
    diamond = _written_models(monkeypatch, "Diamond")
    silicon_carbide = _written_models(monkeypatch, "SiliconCarbide")

    for name in ("TrappedElectrons", "TrappingRate_n", "U_r"):
        assert "ifelse(Electrons > CarrierFloor, Electrons, CarrierFloor)" in diamond[name]
        assert "CarrierFloor" not in silicon_carbide[name]


def test_every_diamond_defect_counts_both_its_trapped_electrons_and_holes(monkeypatch: pytest.MonkeyPatch) -> None:
    models = _written_models(monkeypatch, "Diamond")

    # peiyao counts N f as trapped electrons and N (1 - f) as trapped holes for each defect
    for name in ("BoronAcceptor", "SubstitutionalNitrogen_P1", "VacancyRelated"):
        assert "N_t_irr_" + name in models["TrappedElectrons"]
        assert "N_t_irr_" + name in models["TrappedHoles"]
