from __future__ import annotations

import math

import pytest

from raser.core.field import physics_avalanche
from raser.core.model.material import Material

# Hatakeyama et al., Appl. Phys. Lett. 85 (2004) 1380, 4H-SiC [1/cm, V/cm]
_A = {"n": (1.76e8, 2.10e7), "p": (3.41e8, 2.96e7)}  # a_0001, a_1120
_B = {"n": (3.30e7, 1.70e7), "p": (2.50e7, 1.60e7)}  # b_0001, b_1120


def _hatakeyama(carrier: str, field: float, angle_deg: float, temperature: float) -> float:
    """The anisotropic coefficient of the paper, the field `angle_deg` off <0001>."""
    if field <= 1e4:
        return 0.0
    a0001, a1120 = _A[carrier]
    b0001, b1120 = _B[carrier]
    e0001 = field * math.cos(math.radians(angle_deg))
    e1120 = field * math.sin(math.radians(angle_deg))
    big_b = field / math.sqrt((e1120 / b1120) ** 2 + (e0001 / b0001) ** 2)
    a = a1120 ** ((big_b * e1120 / (b1120 * field)) ** 2) * a0001 ** ((big_b * e0001 / (b0001 * field)) ** 2)
    big_a = math.log(a0001 / a1120)
    b = big_b * math.sqrt(1 - big_a**2 * (big_b * e1120 * e0001 / (field * b1120 * b0001)) ** 2)
    gamma = math.tanh(0.19 / (2 * 0.0257)) / math.tanh(0.19 / (2 * 0.0257 * temperature / 300.0))
    return gamma * a * math.exp(-gamma * b / field)


def _solver_coefficients(field: float, temperature: float) -> tuple[float, float]:
    """Ion_coeff_n, Ion_coeff_p as the solver gets them, evaluated at an edge field."""
    names = {
        "ElectricField": field, "T": temperature,
        "abs": abs, "exp": math.exp, "log": math.log, "pow": math.pow, "tanh": math.tanh,
        "ifelse": lambda condition, if_true, if_false: if_true if condition else if_false,
    }
    electron, hole = physics_avalanche.CreateImpactModel_Hatakeyama("d", "r")
    return (
        eval(electron, {"__builtins__": {}}, names),
        eval(hole, {"__builtins__": {}}, names),
    )


@pytest.mark.parametrize("field", [5e3, 2e6, 3e6])
def test_the_solver_takes_hatakeyama_at_four_degrees(field: float) -> None:
    # The solver keeps its field 1 V/cm off zero: 1e-6 of the field here.
    electron, hole = _solver_coefficients(-field, 300.0)

    assert electron == pytest.approx(_hatakeyama("n", field, 4.0, 300.0), rel=1e-4, abs=0.0)
    assert hole == pytest.approx(_hatakeyama("p", field, 4.0, 300.0), rel=1e-4, abs=0.0)


@pytest.mark.parametrize("field", [5e3, 2e6, 3e6])
def test_the_drift_takes_hatakeyama_along_0001(field: float) -> None:
    coefficient = Material("SiC").cal_coefficient

    assert coefficient(field, -1, 254.0) == pytest.approx(_hatakeyama("n", field, 0.0, 254.0), rel=1e-12)
    assert coefficient(field, +1, 254.0) == pytest.approx(_hatakeyama("p", field, 0.0, 254.0), rel=1e-12)
