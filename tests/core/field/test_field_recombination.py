from __future__ import annotations

import math
from typing import Any

import pytest

from raser.core.field import physics_avalanche, physics_drift_diffusion
from raser.core.model.recombination import SRH, TAT_FIELD_ENHANCEMENT

_BEFORE = "(Electrons*Holes - n_i^2)/(taup*(Electrons + n1) + taun*(Holes + p1))"


def _value(text: str, names: dict[str, float]) -> float:
    return float(eval(text.replace("^", "**"), {"__builtins__": {}}, dict(names)))


@pytest.mark.parametrize(
    "point",
    [
        # depleted: generation; flooded: recombination (Si, 300 K)
        {"Electrons": 1e3, "Holes": 1e2, "n_i": 9.65e9, "n1": 9.65e9, "p1": 9.65e9, "taun": 7e-3, "taup": 7e-3},
        {"Electrons": 1e17, "Holes": 3e16, "n_i": 9.65e9, "n1": 9.65e9, "p1": 9.65e9, "taun": 2.5e-6, "taup": 0.5e-6},
        # a trap off the intrinsic level: n1 and p1 apart
        {"Electrons": 1e12, "Holes": 1e8, "n_i": 9.65e9, "n1": 1e14, "p1": 9.3e5, "taun": 2.5e-6, "taup": 0.5e-6},
    ],
)
def test_the_solver_takes_the_srh_of_core_model(monkeypatch: pytest.MonkeyPatch, point: dict[str, float]) -> None:
    models: dict[str, Any] = {}
    monkeypatch.setattr(physics_drift_diffusion, "CreateNodeModel", lambda d, r, name, text: models.__setitem__(name, text))
    monkeypatch.setattr(physics_drift_diffusion, "CreateNodeModelDerivative", lambda *args: None)
    monkeypatch.setattr(physics_drift_diffusion, "edge_from_node_model", lambda **kwargs: None)

    physics_drift_diffusion.CreateSRH("device", "region", None)

    solver = _value(models["USRH"], point)
    assert solver == _value(_BEFORE, point)
    assert solver == SRH.value(
        n=point["Electrons"], p=point["Holes"], n_i=point["n_i"], n1=point["n1"],
        p1=point["p1"], tau_n=point["taun"], tau_p=point["taup"],
    )


_TAT_BEFORE = (
    "ifelse(abs(ElectricField)<F_sat,2*(3*3.14159)^0.5*abs(ElectricField)/3.9e4*exp((abs(ElectricField)/3.9e4)^2)"
    "*(U_const_n1),2*(3*3.14159)^0.5*abs(F_sat)/3.9e4*exp((F_sat/3.9e4)^2)*(U_const_n1))"
)


@pytest.mark.parametrize("field", [-3e4, 9.9e4, 1.01e5, 3e5])
@pytest.mark.parametrize("saturation", [1e5, 2e5])
def test_the_solver_takes_the_tat_of_core_model(
    monkeypatch: pytest.MonkeyPatch, field: float, saturation: float
) -> None:
    # Hurkx's field enhancement, held at F_sat above it; a device file may set F_sat.
    models: dict[str, str] = {}
    monkeypatch.setattr(physics_avalanche, "CreateEdgeModel", lambda d, r, name, text: models.__setitem__(name, text))
    monkeypatch.setattr(physics_avalanche, "CreateEdgeModelDerivatives", lambda *args: None)
    physics_avalanche.CreateFESRH("device", "region")
    point = {"ElectricField": field, "F_sat": saturation, "U_const_n1": 2.5e12, "abs": abs, "exp": math.exp, "ifelse": lambda c, a, b: a if c else b}

    solver = eval(models["R_TAT"].replace("@n1", "_n1").replace("^", "**"), {"__builtins__": {}}, point)

    assert solver == pytest.approx(eval(_TAT_BEFORE.replace("^", "**"), {"__builtins__": {}}, point), rel=1e-12)
    assert solver == pytest.approx(TAT_FIELD_ENHANCEMENT.value(E=abs(field), F_sat=saturation) * 2.5e12, rel=1e-12)
