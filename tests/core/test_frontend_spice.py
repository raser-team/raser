import numpy as np
import pytest

from raser.core.frontend.spice import solve

pytestmark = pytest.mark.ngspice

LOAD_OHM = 50.0
TAU_S = 10e-12 * LOAD_OHM  # 10 pF sensor on the load
# the current source sits across the 10 pF, between the electrode and ground
FULLY_DEPLETED = ["C1 s1 0 10p", "Rj1 s1 in1 1u", "Rr1 r1 0 1u"]


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

    voltage = solve([wire], times, [step], FULLY_DEPLETED, LOAD_OHM)

    assert voltage.shape == (1, times.size)
    assert voltage[0] == pytest.approx(_rc_step_response(times, 1e-6), abs=5e-8)


def test_each_electrode_answers_its_own_current(wire):
    times = _times()
    step = np.where(times > 0, 1e-6, 0.0)
    sensor = FULLY_DEPLETED + ["C2 s2 0 10p", "Rj2 s2 in2 1u", "Rr2 r2 0 1u"]

    voltage = solve([wire], times, [step, -2 * step], sensor, LOAD_OHM)

    assert voltage[0] == pytest.approx(_rc_step_response(times, 1e-6), abs=5e-8)
    assert voltage[1] == pytest.approx(_rc_step_response(times, -2e-6), abs=1e-7)


def test_circuit_is_at_rest_before_a_current_that_fills_the_first_bin(wire):
    step = 5e-12
    times = (np.arange(1000) + 0.5) * step
    constant = np.full(times.size, 1e-6)

    voltage = solve([wire], times, [constant], FULLY_DEPLETED, LOAD_OHM)

    # the current starts at the left edge of the first bin, t = 0
    assert voltage[0] == pytest.approx(_rc_step_response(times, 1e-6), abs=5e-8)


def test_stages_follow_one_another_from_the_sensor_to_the_load(tmp_path):
    # a buffer with 50 Ohm input and gain 3, then 50 Ohm in series: the sensor
    # sees the 50 Ohm of the buffer, the load halves the buffered voltage
    buffer = tmp_path / "buffer.cir"
    buffer.write_text(
        ".subckt buffer in out\nR1 in 0 50\nE1 out 0 in 0 3\n.ends buffer\n"
    )
    series = tmp_path / "series.cir"
    series.write_text(".subckt series in out\nR1 in out 50\n.ends series\n")
    times = _times()
    step = np.where(times > 0, 1e-6, 0.0)

    voltage = solve([buffer, series], times, [step], FULLY_DEPLETED, LOAD_OHM)

    expected = 1.5 * _rc_step_response(times, 1e-6)
    assert voltage[0] == pytest.approx(expected, abs=7.5e-8)


def test_current_source_sits_between_two_sensor_nodes(wire):
    # sensor that is not fully depleted: the depleted layer C1 from the
    # electrode to an inner node, the undepleted layer R2 parallel C2 from
    # there to ground, the current source across C1. Into a short the
    # electrode current after a step I is I (1 - C1 / (C1 + C2) exp(-t / tau)),
    # tau = R2 (C1 + C2).
    sensor = [
        "C1 in1 inner 10p",
        "R2 inner 0 100",
        "C2 inner 0 20p",
        "Rj1 s1 in1 1u",
        "Rr1 r1 inner 1u",
    ]
    short_ohm = 0.1
    times = -1e-9 + (np.arange(2000) + 0.5) * 5e-12
    step = np.where(times > 0, 1e-3, 0.0)

    voltage = solve([wire], times, [step], sensor, short_ohm)

    after = np.clip(times, 0, None)
    expected = np.where(times > 0, 1 - 10 / 30 * np.exp(-after / 3e-9), 0.0)
    # the current jumps within the first bin after zero: compare off that bin
    off_the_jump = (times < 0) | (times > 5e-12)
    electrode_current = voltage[0] / (-1e-3 * short_ohm)
    assert electrode_current[off_the_jump] == pytest.approx(
        expected[off_the_jump], abs=1e-3
    )
