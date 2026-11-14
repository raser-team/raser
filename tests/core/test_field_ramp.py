from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from raser.core.field import loop_section


@pytest.fixture
def solved(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """The kinds of solve a bias step asks of devsim, in order."""
    kinds: list[str] = []
    devsim = SimpleNamespace(
        error=RuntimeError,
        set_parameter=lambda **_: None,
        circuit_alter=lambda **_: None,
        solve=lambda **asked: kinds.append(asked["type"]),
        get_contact_current=lambda **_: 1.0,
        get_circuit_node_value=lambda **_: 1.0,
    )
    monkeypatch.setattr(loop_section, "devsim", devsim)
    monkeypatch.setattr(
        loop_section.physics_drift_diffusion, "PrintCurrents", lambda **_: None
    )
    return kinds


@pytest.mark.parametrize(
    ("solve_model", "with_noise", "each_step"),
    [
        (None, False, ["dc"]),
        ("cv", False, ["dc", "ac"]),
        (None, True, ["dc", "noise"]),
        ("cv", True, ["dc", "ac", "noise"]),
        ("wf", True, ["dc"]),
    ],
)
def test_every_bias_step_gives_one_value_of_each_curve_that_was_asked_for(
    solved: list[str], solve_model: Any, with_noise: bool, each_step: list[str]
) -> None:
    paras = {
        "absolute_error_VoltageSteps": 1.0,
        "relative_error_VoltageSteps": 1.0,
        "maximum_iterations_VoltageSteps": 1,
        "frequency": 1.0,
    }
    ramp = loop_section.loop_section(paras, "d", "r", solve_model, False, "folder", with_noise)

    for bias in (1.0, 2.0):
        ramp.loop_solver(circuit_contact="top", v_trial=bias, area_factor=1.0)

    assert solved == each_step * 2
    assert ramp.get_voltage_values() == [1.0, 2.0]
    assert len(ramp.get_current_values()) == (0 if solve_model == "wf" else 2)
    assert len(ramp.get_cap_values()) == 2 * each_step.count("ac")
    assert len(ramp.get_noise_values()) == 2 * each_step.count("noise")
