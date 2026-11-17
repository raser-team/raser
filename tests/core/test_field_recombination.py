from __future__ import annotations

from typing import Any

import pytest

from raser.core.field import physics_drift_diffusion
from raser.core.model.recombination import SRH

_BEFORE = "(Electrons*Holes - n_i^2)/(taup*(Electrons + n1) + taun*(Holes + p1))"


def _value(text: str, names: dict[str, float]) -> float:
    return float(eval(text.replace("^", "**"), {"__builtins__": {}}, dict(names)))


@pytest.mark.parametrize(
    "point",
    [
        # depleted: generation; flooded: recombination (Si, 300 K)
        {"Electrons": 1e3, "Holes": 1e2, "n_i": 9.65e9, "n1": 9.65e9, "p1": 9.65e9, "taun": 7e-3, "taup": 7e-3},
        {"Electrons": 1e17, "Holes": 3e16, "n_i": 9.65e9, "n1": 9.65e9, "p1": 9.65e9, "taun": 2.5e-6, "taup": 0.5e-6},
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
