import numpy as np
import pytest

from raser.core.field.device_circuit import DeviceCircuit
from raser.core.readout.spice import output_noise_spectrum
from raser.core.readout.spice import short_circuit_currents
from raser.core.readout.spice import solve
from raser.core.readout.spice import write_netlist

pytestmark = pytest.mark.ngspice

LOAD_OHM = 50.0
TAU_S = 10e-12 * LOAD_OHM  # 10 pF device on the load
DT_S = 5e-12
# the current source sits across the 10 pF, between the electrode and ground
FULLY_DEPLETED = DeviceCircuit(
    lines=("C1 pad 0 10p",), sources={"top": ("pad", "0")}, outputs={"top": "pad"}
)


# an amplifier that is a wire, on a resistive load: the device sees the load
WIRE = {
    "ports": {"in": "a", "out": "b"},
    "elements": {"R1": {"between": ["a", "b"], "ohm": 1e-6}},
}
LOAD = {
    "ports": {"in": "a"},
    "elements": {"R1": {"between": ["a", "0"], "ohm": LOAD_OHM}},
}
ON_THE_LOAD = {"stages": {"wire": WIRE}, "load": LOAD}


def _times():
    # starts before zero, as the current of a 2D device does
    return -1e-9 + (np.arange(1000) + 0.5) * DT_S


def _rc_step_response(times, current_a):
    """Voltage on R parallel C for a current step at t = 0 drawn out of the node."""
    return -current_a * LOAD_OHM * (1 - np.exp(-np.clip(times, 0, None) / TAU_S))


def test_rc_step_response_on_the_time_axis_of_the_current():
    times = _times()
    step = np.where(times > 0, 1e-6, 0.0)

    voltage = solve(ON_THE_LOAD, ["top"], DT_S, [step], FULLY_DEPLETED)

    assert voltage.shape == (1, times.size)
    assert voltage[0] == pytest.approx(_rc_step_response(times, 1e-6), abs=5e-8)


def test_each_electrode_answers_its_own_current():
    # the right electrode has twice the capacitance, so twice the time constant
    circuit = DeviceCircuit(
        lines=("C1 a 0 10p", "C2 b 0 20p"),
        sources={"left": ("a", "0"), "right": ("b", "0")},
        outputs={"left": "a", "right": "b"},
    )
    times = _times()
    step = np.where(times > 0, 1e-6, 0.0)
    after = np.clip(times, 0, None)

    # the currents come in another order than the circuit names its outputs,
    # which give the order of the voltages
    voltage = solve(ON_THE_LOAD, ["right", "left"], DT_S, [-2 * step, step], circuit)

    right = 2e-6 * LOAD_OHM * (1 - np.exp(-after / (2 * TAU_S)))
    assert voltage[1] == pytest.approx(right, abs=1e-7)
    assert voltage[0] == pytest.approx(_rc_step_response(times, 1e-6), abs=5e-8)


def test_currents_on_cells_are_read_out_on_a_strip_they_lie_beside():
    # two cells of a resistive layer, each with 1 pF to the back: the near one
    # is under the strip, the far one 10 kOhm away from it. Each brings 1 fC;
    # all of it leaves through the 50 Ohm load of the strip, that of the far
    # cell later, after it has crossed the 10 kOhm
    circuit = DeviceCircuit(
        lines=("Cnear strip 0 1p", "Cfar far 0 1p", "Rlayer far strip 10k"),
        sources={"near": ("0", "strip"), "far": ("0", "far")},
        outputs={"strip": "strip"},
    )
    dt = 20e-12
    times = (np.arange(10000) + 0.5) * dt
    pulse = np.where((times > 0.1e-9) & (times < 0.2e-9), 1e-15 / 0.1e-9, 0.0)
    quiet = np.zeros(times.size)

    near = solve(ON_THE_LOAD, ["near", "far"], dt, [pulse, quiet], circuit)
    far = solve(ON_THE_LOAD, ["far", "near"], dt, [pulse, quiet], circuit)

    assert near.shape == far.shape == (1, times.size)
    for voltage in (near[0], far[0]):
        assert np.sum(voltage) * dt / LOAD_OHM == pytest.approx(1e-15, rel=0.01, abs=0)
    # the far cell empties through 10 kOhm into the strip: in about 10 ns,
    # the near one through the load in less than one
    arrival = [np.sum(times * v[0]) / np.sum(v[0]) for v in (near, far)]
    assert arrival[0] < 1e-9
    assert arrival[1] == pytest.approx(10e-9, rel=0.1)
    with pytest.raises(ValueError, match="current sources"):
        solve(ON_THE_LOAD, ["strip"], dt, [pulse], circuit)


def test_circuit_is_at_rest_before_a_current_that_fills_the_first_bin():
    step = 5e-12
    times = (np.arange(1000) + 0.5) * step
    constant = np.full(times.size, 1e-6)

    voltage = solve(ON_THE_LOAD, ["top"], step, [constant], FULLY_DEPLETED)

    # the current starts at the left edge of the first bin, t = 0
    assert voltage[0] == pytest.approx(_rc_step_response(times, 1e-6), abs=5e-8)


def test_stages_follow_one_another_from_the_sensor_to_the_load():
    # 100 Ohm in series, then 100 Ohm across the line, then the 100 Ohm load:
    # the 10 pF device sees 150 Ohm, the load a third of its voltage
    series = {
        "ports": {"in": "a", "out": "b"},
        "elements": {"R1": {"between": ["a", "b"], "ohm": 100.0}},
    }
    across = {
        "ports": {"in": "a", "out": "b"},
        "elements": {
            "R1": {"between": ["a", "0"], "ohm": 100.0},
            "R2": {"between": ["a", "b"], "ohm": 1e-6},
        },
    }
    load = {
        "ports": {"in": "a"},
        "elements": {"R1": {"between": ["a", "0"], "ohm": 100.0}},
    }
    chain = {"stages": {"series": series, "across": across}, "load": load}
    times = _times()
    step = np.where(times > 0, 1e-6, 0.0)

    voltage = solve(chain, ["top"], DT_S, [step], FULLY_DEPLETED)

    after = np.clip(times, 0, None)
    expected = -1e-6 * 50.0 * (1 - np.exp(-after / (150.0 * 10e-12)))
    assert voltage[0] == pytest.approx(expected, abs=5e-8)


def test_short_circuit_current_of_a_sensor_that_is_not_fully_depleted():
    # the depleted layer C1 from the electrode to an inner node, the
    # undepleted layer R2 parallel C2 from there to ground, the current source
    # across C1, drawing the current I out of the electrode after t = 0. The
    # short then feeds I (1 - C1 / (C1 + C2) exp(-t / tau)) into the electrode,
    # tau = R2 (C1 + C2).
    circuit = DeviceCircuit(
        lines=("C1 pad inner 10p", "R2 inner 0 100", "C2 inner 0 20p"),
        sources={"top": ("pad", "inner")},
        outputs={"top": "pad"},
    )
    times = -1e-9 + (np.arange(2000) + 0.5) * DT_S
    step = np.where(times > 0, 1e-6, 0.0)

    into_short = short_circuit_currents(["top"], DT_S, [step], circuit)

    after = np.clip(times, 0, None)
    expected = -1e-6 * np.where(times > 0, 1 - 10 / 30 * np.exp(-after / 3e-9), 0.0)
    # the current jumps within the first bin after zero: compare off that bin
    off_the_jump = (times < 0) | (times > 5e-12)
    assert into_short.shape == (1, times.size)
    assert into_short[0][off_the_jump] == pytest.approx(
        expected[off_the_jump], abs=1e-9
    )


def test_output_noise_of_a_resistor_on_a_capacitor():
    # each electrode has its capacitance on the 50 Ohm load, at 300.15 K: the
    # noise is that of the resistor, sqrt(4 k T R), up to 1 / (2 pi R C), and
    # its rms is sqrt(k T / C) whatever the resistor
    circuit = DeviceCircuit(
        lines=("C1 a 0 10p", "C2 b 0 40p"),
        sources={"left": ("0", "a"), "right": ("0", "b")},
        outputs={"left": "a", "right": "b"},
    )
    k_t = 1.380649e-23 * 300.15

    frequencies, density = output_noise_spectrum(ON_THE_LOAD, circuit, 1e3, 1e13)

    assert density[:, 0] == pytest.approx(np.sqrt(4 * k_t * LOAD_OHM), rel=1e-3)
    power = density**2
    # trapezoids between the frequencies
    rms = np.sqrt(
        np.sum((power[:, 1:] + power[:, :-1]) / 2 * np.diff(frequencies), axis=1)
    )
    assert rms == pytest.approx(np.sqrt(k_t / np.array([10e-12, 40e-12])), rel=5e-3)


def test_chain_without_a_stage_has_the_load_on_the_sensor():
    times = _times()
    step = np.where(times > 0, 1e-6, 0.0)

    voltage = solve({"stages": {}, "load": LOAD}, ["top"], DT_S, [step], FULLY_DEPLETED)

    assert voltage[0] == pytest.approx(_rc_step_response(times, 1e-6), abs=5e-8)


def test_a_run_keeps_only_the_outputs_it_writes(tmp_path):
    # ngspice keeps every node of every step unless told which: a row of some
    # hundred strips does not fit
    circuit = DeviceCircuit(
        lines=("C1 a 0 10p", "C2 b 0 20p"),
        sources={"left": ("a", "0"), "right": ("b", "0")},
        outputs={"left": "a", "right": "b"},
    )
    netlist = write_netlist(
        ON_THE_LOAD, ["left", "right"], DT_S, np.zeros((2, 10)), circuit, tmp_path / "x"
    )

    saved = [line for line in netlist.splitlines() if line.startswith(".save")]
    assert saved == [".save v(out1) v(out2)"]
