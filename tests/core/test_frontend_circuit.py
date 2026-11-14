import numpy as np
import pytest

from raser.core.frontend.circuit import subcircuit
from raser.core.frontend.planar_sensor import planar_sensor
from raser.core.frontend.spice import solve

pytestmark = pytest.mark.ngspice

DT_S = 5e-12


def test_stage_and_load_written_from_their_description(tmp_path):
    # the stage puts 100 Ohm and 10 pF across its input and reaches its output
    # through 100 Ohm; with the 100 Ohm load and the 10 pF sensor the electrode
    # sees 100 Ohm parallel to 200 Ohm and 20 pF, and the load half its voltage
    stage = {
        "ports": {"in": "a", "out": "b"},
        "elements": {
            "R1": {"between": ["a", "0"], "ohm": 100.0},
            "C1": {"between": ["a", "0"], "farad": 10e-12},
            "R2": {"between": ["a", "b"], "ohm": 100.0},
        },
    }
    load = {
        "ports": {"in": "a"},
        "elements": {"R1": {"between": ["a", "0"], "ohm": 100.0}},
    }
    stage_file = tmp_path / "shunt.cir"
    stage_file.write_text(subcircuit("shunt", stage))
    load_file = tmp_path / "resistor.cir"
    load_file.write_text(subcircuit("resistor", load))
    times = -1e-9 + (np.arange(1000) + 0.5) * DT_S
    step = np.where(times > 0, 1e-6, 0.0)

    voltage = solve(
        [stage_file], ["top"], DT_S, [step], planar_sensor("top", 10e-12), load_file
    )

    after = np.clip(times, 0, None)
    seen_ohm = 100.0 * 200.0 / 300.0
    expected = 1e-6 * seen_ohm / 2 * (1 - np.exp(-after / (seen_ohm * 20e-12)))
    off_the_jump = (times < 0) | (times > DT_S)
    assert voltage[0][off_the_jump] == pytest.approx(expected[off_the_jump], abs=3e-8)


def test_element_without_a_quantity_is_refused():
    stage = {"ports": {"in": "a"}, "elements": {"R1": {"between": ["a", "0"]}}}

    with pytest.raises(ValueError, match="Element R1 of load"):
        subcircuit("load", stage)
