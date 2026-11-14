import numpy as np
import pytest

from raser.core.frontend.spice import solve

pytestmark = pytest.mark.ngspice

LOAD_OHM = 50.0
TAU_S = 10e-12 * LOAD_OHM  # 10 pF sensor on the load


@pytest.fixture
def wire(tmp_path):
    """An amplifier that is a wire: the sensor sees the load directly."""
    circuit = tmp_path / "wire.cir"
    circuit.write_text(".subckt wire in out\nR1 in out 1u\n.ends wire\n")
    return circuit


def _times():
    # starts before zero, as the current of a 2D device does
    return -1e-9 + (np.arange(1000) + 0.5) * 5e-12


def _rc_step_response(times, current_a):
    """Voltage on R parallel C for a current step at t = 0 drawn out of the node."""
    return -current_a * LOAD_OHM * (1 - np.exp(-np.clip(times, 0, None) / TAU_S))


def test_rc_step_response_on_the_time_axis_of_the_current(wire):
    times = _times()
    step = np.where(times > 0, 1e-6, 0.0)

    voltage = solve(wire, times, [step], ["C1 s1 0 10p", "Rj1 s1 in1 1u"], LOAD_OHM)

    assert voltage.shape == (1, times.size)
    assert voltage[0] == pytest.approx(_rc_step_response(times, 1e-6), abs=5e-8)


def test_each_electrode_answers_its_own_current(wire):
    times = _times()
    step = np.where(times > 0, 1e-6, 0.0)
    sensor = ["C1 s1 0 10p", "Rj1 s1 in1 1u", "C2 s2 0 10p", "Rj2 s2 in2 1u"]

    voltage = solve(wire, times, [step, -2 * step], sensor, LOAD_OHM)

    assert voltage[0] == pytest.approx(_rc_step_response(times, 1e-6), abs=5e-8)
    assert voltage[1] == pytest.approx(_rc_step_response(times, -2e-6), abs=1e-7)
