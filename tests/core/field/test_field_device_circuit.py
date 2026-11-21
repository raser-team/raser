import numpy as np
import pytest

from raser.core.field.circuit_parameters import undepleted_layer
from raser.core.field.device_circuit import planar_circuit, side_by_side
from raser.core.readout.spice import short_circuit_currents, solve

pytestmark = pytest.mark.ngspice

# the device of W. Riegler, arXiv:1812.07570, section 5: silicon of 5 kOhm cm,
# 300 um thick, depleted over 200 um, 1 cm2
PERMITTIVITY_F_PER_M = 11.9 * 8.8541878128e-12
AREA_M2 = 1e-4
THICKNESS_M = 300e-6
DEPLETED_M = 200e-6
RESISTIVITY_OHM_M = 50.0
DT_S = 20e-12


def _step():
    times = -1e-9 + (np.arange(2500) + 0.5) * DT_S
    return times, np.where(times > 0, 1e-6, 0.0)


def test_short_circuit_current_of_a_sensor_that_is_not_fully_depleted():
    # a step I of induced current reaches the electrode as
    # I (1 - (1 - w / d) exp(-t / tau)), tau = permittivity resistivity d / w:
    # 7.9 ns in the paper
    depleted_f = PERMITTIVITY_F_PER_M * AREA_M2 / DEPLETED_M
    undepleted = undepleted_layer(
        AREA_M2, THICKNESS_M, DEPLETED_M, PERMITTIVITY_F_PER_M, RESISTIVITY_OHM_M
    )
    times, step = _step()

    into_short = short_circuit_currents(
        ["top"], DT_S, [step], planar_circuit("top", depleted_f, undepleted)
    )

    tau = PERMITTIVITY_F_PER_M * RESISTIVITY_OHM_M * THICKNESS_M / DEPLETED_M
    assert tau == pytest.approx(7.9e-9, rel=0.01)
    after = np.clip(times, 0, None)
    expected = 1e-6 * np.where(
        times > 0, 1 - (1 - DEPLETED_M / THICKNESS_M) * np.exp(-after / tau), 0.0
    )
    # the current jumps within the first bin after zero: compare off that bin
    off_the_jump = (times < 0) | (times > DT_S)
    assert into_short[0][off_the_jump] == pytest.approx(
        expected[off_the_jump], abs=1e-9
    )


def test_short_circuit_current_of_a_fully_depleted_sensor_is_the_induced_current():
    times, step = _step()
    depleted_f = PERMITTIVITY_F_PER_M * AREA_M2 / THICKNESS_M

    into_short = short_circuit_currents(
        ["top"], DT_S, [step], planar_circuit("top", depleted_f)
    )

    assert into_short[0] == pytest.approx(step, abs=1e-9)


def test_coupling_capacitance_shares_the_current_with_the_depleted_layer():
    # 10 pF depleted layer, 100 Ohm to the bias, 90 pF to the read-out, which
    # is shorted: of a step I the read-out gets I 90 / (10 + 90) at first, and
    # the bias resistance takes it over with tau = 100 Ohm (10 pF + 90 pF)
    circuit = planar_circuit(
        "top", 10e-12, bias_resistance_ohm=100.0, coupling_capacitance_f=90e-12
    )
    times, step = _step()

    into_short = short_circuit_currents(["top"], DT_S, [step], circuit)

    after = np.clip(times, 0, None)
    expected = 1e-6 * np.where(times > 0, 0.9 * np.exp(-after / 10e-9), 0.0)
    off_the_jump = (times < 0) | (times > DT_S)
    assert into_short[0][off_the_jump] == pytest.approx(
        expected[off_the_jump], abs=1e-9
    )


def test_bias_resistance_lies_between_the_electrode_and_ground():
    # read out DC-coupled by a wire on a 50 Ohm load: the electrode sees the
    # 50 Ohm bias resistance parallel to the load, 25 Ohm, with its 10 pF
    chain = {
        "stages": {
            "wire": {
                "ports": {"in": "a", "out": "b"},
                "elements": {"R1": {"between": ["a", "b"], "ohm": 1e-6}},
            }
        },
        "load": {
            "ports": {"in": "a"},
            "elements": {"R1": {"between": ["a", "0"], "ohm": 50.0}},
        },
    }
    circuit = planar_circuit("top", 10e-12, bias_resistance_ohm=50.0)
    times, step = _step()

    voltage = solve(chain, ["top"], DT_S, [step], circuit)

    after = np.clip(times, 0, None)
    expected = 1e-6 * 25.0 * (1 - np.exp(-after / (25.0 * 10e-12)))
    off_the_jump = (times < 0) | (times > DT_S)
    assert voltage[0][off_the_jump] == pytest.approx(expected[off_the_jump], abs=2.5e-8)


def test_electrodes_side_by_side_each_answer_with_their_own_sensor():
    # a step on the electrode of 10 pF, read through 1 nF beside 1 MOhm: the
    # 1 nF carries 1000 / 1010 of it into the short; twice the step on its
    # neighbour of 40 pF, read as it is: all of it
    times, step = _step()
    circuit = side_by_side(
        [
            planar_circuit("near", 10e-12, None, 1e6, 1e-9),
            planar_circuit("far", 40e-12),
        ]
    )

    into_short = short_circuit_currents(
        ["far", "near"], DT_S, [2 * step, step], circuit
    )

    # the shorts come in the order of the outputs of the circuit
    off_the_jump = (times < 0) | (times > DT_S)
    expected = np.where(times > 0, 1e-6, 0.0)[off_the_jump]
    assert into_short[1][off_the_jump] == pytest.approx(2 * expected, abs=2e-9)
    assert into_short[0][off_the_jump] == pytest.approx(
        expected * 1000 / 1010, abs=2e-9
    )
    with pytest.raises(ValueError, match="near"):
        side_by_side([planar_circuit("near", 1e-12), planar_circuit("near", 2e-12)])
