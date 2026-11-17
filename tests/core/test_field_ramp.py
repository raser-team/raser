from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from raser.core.field import loop_section
from raser.core.field.solver_section import _resolve_impact_model
from raser.core.field.solver_section import _voltage_milestones


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
        get_node_model_values=lambda **_: [0.0],
        set_node_values=lambda **_: None,
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


def _ramp_on_a_line(monkeypatch: pytest.MonkeyPatch, fails_at: float | None = None):
    """A ramp over a fake devsim whose solution at a bias is bias * (0, 0.5, 1)
    for the potential and bias + 1 for both carriers. Returns the ramp and the
    list of what every solve started from."""
    state = {"Potential": [9.0, 9.0, 9.0], "Electrons": [9.0] * 3, "Holes": [9.0] * 3}
    bias = {"value": 0.0}
    started: list[dict[str, list[float]]] = []

    def solve(**_: Any) -> None:
        started.append({name: list(values) for name, values in state.items()})
        if bias["value"] == fails_at:
            for name in state:
                state[name] = [-7.0, -7.0, -7.0]  # what a failed solve leaves behind
            raise RuntimeError("Convergence failure")
        state["Potential"] = [bias["value"] * x for x in (0.0, 0.5, 1.0)]
        state["Electrons"] = state["Holes"] = [bias["value"] + 1.0] * 3

    def set_parameter(**given: Any) -> None:
        bias["value"] = given["value"]

    def set_node_values(**given: Any) -> None:
        state[given["name"]] = list(given["values"])

    devsim = SimpleNamespace(
        error=RuntimeError,
        set_parameter=set_parameter,
        solve=solve,
        get_contact_current=lambda **_: 1.0,
        get_node_model_values=lambda **asked: state[asked["name"]],
        set_node_values=set_node_values,
        write_devices=lambda **_: None,
    )
    monkeypatch.setattr(loop_section, "devsim", devsim)
    monkeypatch.setattr(
        loop_section.physics_drift_diffusion, "PrintCurrents", lambda **_: None
    )
    paras = {
        "absolute_error_VoltageSteps": 1.0,
        "relative_error_VoltageSteps": 1.0,
        "maximum_iterations_VoltageSteps": 1,
    }
    ramp = loop_section.loop_section(paras, "d", "r", None, False, "folder")
    return ramp, started


def test_a_bias_step_starts_from_the_potential_carried_on_along_the_last_two_biases(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ramp, started = _ramp_on_a_line(monkeypatch)

    for bias in (0.0, 1.0, 3.0):
        ramp.loop_solver(circuit_contact="top", v_trial=bias, area_factor=1.0)

    # from 0 V and 1 V on to 3 V: the potential of 3 V itself, the carriers of 1 V
    assert started[2] == {
        "Potential": [0.0, 1.5, 3.0],
        "Electrons": [2.0, 2.0, 2.0],
        "Holes": [2.0, 2.0, 2.0],
    }


def test_the_try_after_a_failed_step_starts_from_the_solved_biases_again(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ramp, started = _ramp_on_a_line(monkeypatch, fails_at=3.0)

    for bias in (0.0, 1.0):
        ramp.loop_solver(circuit_contact="top", v_trial=bias, area_factor=1.0)
    with pytest.raises(RuntimeError):
        ramp.loop_solver(circuit_contact="top", v_trial=3.0, area_factor=1.0)
    ramp.loop_solver(circuit_contact="top", v_trial=2.0, area_factor=1.0)

    assert started[3] == {
        "Potential": [0.0, 1.0, 2.0],
        "Electrons": [2.0, 2.0, 2.0],
        "Holes": [2.0, 2.0, 2.0],
    }


def test_field_solver_uses_enabled_avalanche_and_includes_final_bias() -> None:
    disabled = SimpleNamespace(has_avalanche=False, avalanche_model="vanOverstraeten")
    enabled = SimpleNamespace(has_avalanche=True, avalanche_model="vanOverstraeten")

    assert _resolve_impact_model(disabled) is None
    assert _resolve_impact_model(enabled) == "vanOverstraeten"
    assert _voltage_milestones(350.0, 100.0) == [100.0, 200.0, 300.0, 350.0]
    assert _voltage_milestones(-250.0, 100.0) == [-100.0, -200.0, -250.0]
