import math

import pytest

from raser.core.field.physics_avalanche import CreateImpactModel_vanOvenstraeten
from raser.core.model.impact_ionization import VAN_OVERSTRAETEN


def _devsim_value(text: str, field: float, temperature: float) -> float:
    """The value of a devsim expression of ElectricField and T, by a plain evaluation."""
    names = {
        "ElectricField": field,
        "T": temperature,
        "abs": abs,
        "exp": math.exp,
        "tanh": math.tanh,
        "pow": math.pow,
        "ifelse": lambda condition, if_true, if_false: if_true if condition else if_false,
    }
    return float(eval(text.replace("^", "**"), {"__builtins__": {}}, names))


@pytest.mark.parametrize("field", [174999.5, 175000.5, 399999.5, 400000.5, 3e5])
def test_the_solver_takes_the_van_overstraeten_of_the_drift(field: float) -> None:
    # Either side of the 1.75e5 V/cm cut and of E0 = 4e5 V/cm, where holes change
    # from the low- to the high-field set (0.9% apart at E0). The solver keeps
    # its field 1 V/cm above zero only in b/E: 4e-5 at most here.
    electron, hole = CreateImpactModel_vanOvenstraeten("device", "region")

    for text, carrier in ((electron, "electron"), (hole, "hole")):
        drift = VAN_OVERSTRAETEN[carrier].value(E=field, T=300.0)
        assert _devsim_value(text, -field, 300.0) == pytest.approx(drift, rel=1e-4, abs=0.0)
