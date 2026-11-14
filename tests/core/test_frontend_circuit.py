import numpy as np
import pytest

from raser.core.frontend.circuit import read_subcircuit
from raser.core.frontend.circuit import spice_number
from raser.core.frontend.circuit import subcircuit
from raser.core.frontend.planar_sensor import planar_sensor
from raser.core.frontend.spice import solve
from raser.supports.paths import component_path

pytestmark = pytest.mark.ngspice

DT_S = 5e-12


def test_stage_and_load_written_from_their_description():
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
    times = -1e-9 + (np.arange(1000) + 0.5) * DT_S
    step = np.where(times > 0, 1e-6, 0.0)

    voltage = solve(
        {"stages": {"shunt": stage}, "load": load},
        ["top"],
        DT_S,
        [step],
        planar_sensor("top", 10e-12),
    )

    after = np.clip(times, 0, None)
    seen_ohm = 100.0 * 200.0 / 300.0
    expected = 1e-6 * seen_ohm / 2 * (1 - np.exp(-after / (seen_ohm * 20e-12)))
    off_the_jump = (times < 0) | (times > DT_S)
    assert voltage[0][off_the_jump] == pytest.approx(expected[off_the_jump], abs=3e-8)


def test_stage_with_one_node_as_input_and_output_is_refused():
    stage = {
        "ports": {"in": "a", "out": "a"},
        "elements": {"R1": {"between": ["a", "0"], "ohm": 50.0}},
    }

    with pytest.raises(ValueError, match="stage shunt has the node a as input"):
        subcircuit("shunt", stage)


def test_element_without_a_quantity_is_refused():
    stage = {"ports": {"in": "a"}, "elements": {"R1": {"between": ["a", "0"]}}}

    with pytest.raises(ValueError, match="Element R1 of load"):
        subcircuit("load", stage)


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("3.3n", 3.3e-9),
        ("10nF", 10e-9),
        ("47U", 47e-6),
        ("3k", 3e3),
        ("1MEG", 1e6),
        ("1m", 1e-3),
        ("2.25", 2.25),
        ("1e-3", 1e-3),
    ],
)
def test_spice_number(text, value):
    assert spice_number(text) == pytest.approx(value, rel=1e-12)


SHAPER = """* a stage with a model of its own
.subckt series100 a b
R1 a b 100
.ends series100

.subckt shaper in out
Rshunt in 0 100   ; across the input
Cshunt in 0 10p
X1 in out series100
.ends shaper
"""


def test_stage_read_from_its_spice_file(tmp_path):
    # the stage of the test above, written as SPICE: 100 Ohm and 10 pF across
    # its input, 100 Ohm in series to its output, on a 100 Ohm load
    path = tmp_path / "shaper.cir"
    path.write_text(SHAPER)
    load = {
        "ports": {"in": "a"},
        "elements": {"R1": {"between": ["a", "0"], "ohm": 100.0}},
    }
    times = -1e-9 + (np.arange(1000) + 0.5) * DT_S
    step = np.where(times > 0, 1e-6, 0.0)

    stage = read_subcircuit(path)
    voltage = solve(
        {"stages": {"shaper": stage}, "load": load},
        ["top"],
        DT_S,
        [step],
        planar_sensor("top", 10e-12),
    )

    assert stage["elements"]["Rshunt"] == {"between": ["in", "0"], "ohm": 100.0}
    after = np.clip(times, 0, None)
    seen_ohm = 100.0 * 200.0 / 300.0
    expected = 1e-6 * seen_ohm / 2 * (1 - np.exp(-after / (seen_ohm * 20e-12)))
    off_the_jump = (times < 0) | (times > DT_S)
    assert voltage[0][off_the_jump] == pytest.approx(expected[off_the_jump], abs=3e-8)


def test_element_the_description_cannot_hold_is_refused(tmp_path):
    path = tmp_path / "stage.cir"
    path.write_text(".subckt stage in out\nQ1 out in 0 some_transistor\n.ends stage\n")

    with pytest.raises(ValueError, match="Cannot read the element 'Q1 out in 0"):
        read_subcircuit(path)


def test_santa_cruz_inverts_with_a_transimpedance_below_its_feedback_resistor():
    # a transimpedance stage turns the charge Q into an output of area -Z Q;
    # with a finite gain Z stays below the 475 Ohm feedback resistor
    stage = read_subcircuit(component_path("afe", "SantaCruz.cir"))
    load = {
        "ports": {"in": "a"},
        "elements": {"R": {"between": ["a", "0"], "ohm": 50.0}},
    }
    dt = 2e-12
    charge = 1e-15
    impulse = np.zeros(2000)
    impulse[100] = charge / dt

    voltage = solve(
        {"stages": {"SantaCruz": stage}, "load": load},
        ["top"],
        dt,
        [impulse],
        planar_sensor("top", 5e-12),
    )

    transimpedance = -voltage[0].sum() * dt / charge
    assert 0.8 * 475 < transimpedance < 475


BUFFER = """* 50 Ohm at the input, three times its voltage behind 50 Ohm at the output
.subckt buffer in out
Rin in 0 50
E1 inner 0 in 0 3
Rout inner out 50
.ends buffer
"""


def test_gain_follows_the_voltage_at_its_input(tmp_path):
    # the 10 pF sensor sees the 50 Ohm of the input alone; the 50 Ohm load
    # gets half of three times that voltage
    path = tmp_path / "buffer.cir"
    path.write_text(BUFFER)
    load = {
        "ports": {"in": "a"},
        "elements": {"R1": {"between": ["a", "0"], "ohm": 50.0}},
    }
    times = -1e-9 + (np.arange(1000) + 0.5) * DT_S
    step = np.where(times > 0, 1e-6, 0.0)

    stage = read_subcircuit(path)
    voltage = solve(
        {"stages": {"buffer": stage}, "load": load},
        ["top"],
        DT_S,
        [step],
        planar_sensor("top", 10e-12),
    )

    assert stage["elements"]["E1"]["gain"] == 3.0
    after = np.clip(times, 0, None)
    expected = 1.5 * 1e-6 * 50.0 * (1 - np.exp(-after / (50.0 * 10e-12)))
    off_the_jump = (times < 0) | (times > DT_S)
    assert voltage[0][off_the_jump] == pytest.approx(expected[off_the_jump], abs=7.5e-8)


def test_gali52_gives_20_8_db_on_50_ohm_and_3_db_less_at_2_ghz():
    # behind a source of 50 Ohm: a step of 1 uA in the 25 Ohm of source and
    # input is 25 uV, and comes out on the 50 Ohm load 10^(20.8/20) times
    # larger, with the time constant of a 2.0 GHz pole
    source = {
        "ports": {"in": "a", "out": "b"},
        "elements": {
            "R": {"between": ["a", "0"], "ohm": 50.0},
            "wire": {"between": ["a", "b"], "ohm": 1e-6},
        },
    }
    load = {
        "ports": {"in": "a"},
        "elements": {"R": {"between": ["a", "0"], "ohm": 50.0}},
    }
    chain = {
        "stages": {
            "source": source,
            "Gali52": read_subcircuit(component_path("afe", "Gali52.cir")),
        },
        "load": load,
    }
    dt = 2e-12
    times = -0.2e-9 + (np.arange(1000) + 0.5) * dt
    step = np.where(times > 0, 1e-6, 0.0)

    voltage = solve(chain, ["top"], dt, [step], planar_sensor("top", 1e-15))

    after = np.clip(times, 0, None)
    gain = 10 ** (20.8 / 20)
    expected = gain * 25e-6 * (1 - np.exp(-after * 2 * np.pi * 2.0e9))
    off_the_jump = (times < 0) | (times > 2 * dt)
    assert voltage[0][off_the_jump] == pytest.approx(expected[off_the_jump], abs=3e-6)
