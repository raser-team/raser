import numpy as np
import pytest

from raser.core.readout.circuit import named_chain
from raser.core.readout.circuit import read_chain
from raser.core.readout.circuit import read_subcircuit
from raser.core.readout.circuit import spice_number
from raser.core.readout.circuit import subcircuit
from raser.core.field.device_circuit import planar_circuit
from raser.core.readout.spice import output_noise_spectrum
from raser.core.readout.spice import solve
from raser.supports.paths import component_path

pytestmark = pytest.mark.ngspice

DT_S = 5e-12


def test_stage_and_load_written_from_their_description():
    # the stage puts 100 Ohm and 10 pF across its input and reaches its output
    # through 100 Ohm; with the 100 Ohm load and the 10 pF device the electrode
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
        planar_circuit("top", 10e-12),
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
        planar_circuit("top", 10e-12),
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
        planar_circuit("top", 5e-12),
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
    # the 10 pF device sees the 50 Ohm of the input alone; the 50 Ohm load
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
        planar_circuit("top", 10e-12),
    )

    assert stage["elements"]["E1"]["gain"] == 3.0
    after = np.clip(times, 0, None)
    expected = 1.5 * 1e-6 * 50.0 * (1 - np.exp(-after / (50.0 * 10e-12)))
    off_the_jump = (times < 0) | (times > DT_S)
    assert voltage[0][off_the_jump] == pytest.approx(expected[off_the_jump], abs=7.5e-8)


@pytest.mark.parametrize(
    ("frequency_hz", "gain_db"),
    [(100e6, 22.84), (1e9, 20.76), (2e9, 17.95)],
)
def test_gali52_has_the_gain_its_maker_gives(frequency_hz, gain_db):
    # behind a source of 50 Ohm, on a 50 Ohm load: a sine of current I in the
    # 25 Ohm of source and input is the input voltage 25 Ohm I
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
    dt = 1 / frequency_hz / 100
    times = (np.arange(3000) + 0.5) * dt
    sine = np.sin(2 * np.pi * frequency_hz * times)

    voltage = solve(chain, ["top"], dt, [1e-6 * sine], planar_circuit("top", 1e-15))

    settled = voltage[0][2000:]
    amplitude = (settled.max() - settled.min()) / 2
    assert 20 * np.log10(amplitude / 25e-6) == pytest.approx(gain_db, abs=0.25)
    if frequency_hz == 100e6:
        # at low frequency the output is the opposite of the input
        assert np.mean(settled * sine[2000:]) < -0.45 * amplitude


def _chain_files(folder):
    (folder / "series.cir").write_text(
        ".subckt series in out\nR1 in out 100\n.ends series\n"
    )
    (folder / "across.cir").write_text(
        ".subckt across in out\nR1 in 0 100\nR2 in out 1u\n.ends across\n"
    )
    (folder / "load.cir").write_text(".subckt load in\nR1 in 0 300\n.ends load\n")
    return {name: folder / f"{name}.cir" for name in ("series", "across", "load")}


def _step_response(chain):
    times = -1e-9 + (np.arange(1000) + 0.5) * DT_S
    step = np.where(times > 0, 1e-6, 0.0)
    voltage = solve(chain, ["top"], DT_S, [step], planar_circuit("top", 10e-12))
    off_the_jump = (times < 0) | (times > DT_S)
    return np.clip(times, 0, None)[off_the_jump], voltage[0][off_the_jump]


def test_chain_of_stages_in_the_order_of_their_files(tmp_path):
    # 100 Ohm in series, then 100 Ohm across the line, then the 300 Ohm load:
    # the 10 pF device sees 175 Ohm, the load the voltage on the 75 Ohm
    files = _chain_files(tmp_path)

    chain = read_chain([files["series"], files["across"], files["load"]])
    after, voltage = _step_response(chain)

    assert list(chain["stages"]) == ["series", "across"]
    expected = 1e-6 * 75.0 * (1 - np.exp(-after / (175.0 * 10e-12)))
    assert voltage == pytest.approx(expected, abs=5e-8)


def test_chain_with_the_same_stage_twice(tmp_path):
    files = _chain_files(tmp_path)

    chain = read_chain(
        [files["across"], files["series"], files["series"], files["load"]]
    )
    after, voltage = _step_response(chain)

    assert list(chain["stages"]) == ["across", "series", "series_2"]
    # 100 Ohm across the line, beside the 500 Ohm of the rest
    expected = 1e-6 * 50.0 * (1 - np.exp(-after / (500.0 / 6 * 10e-12)))
    assert voltage == pytest.approx(expected, abs=5e-8)


def test_chain_with_two_stages_of_one_name_from_two_folders(tmp_path):
    # the 100 Ohm in series, then a stage of the same name that lies across
    # the line: as the series and the across stages of the first test
    files = _chain_files(tmp_path)
    (tmp_path / "other").mkdir()
    other = tmp_path / "other" / "series.cir"
    other.write_text(".subckt series in out\nR1 in 0 100\nR2 in out 1u\n.ends series\n")

    chain = read_chain([files["series"], other, files["load"]])
    after, voltage = _step_response(chain)

    assert list(chain["stages"]) == ["series", "series_2"]
    expected = 1e-6 * 75.0 * (1 - np.exp(-after / (175.0 * 10e-12)))
    assert voltage == pytest.approx(expected, abs=5e-8)


def test_chain_that_does_not_end_in_its_only_load_is_refused(tmp_path):
    files = _chain_files(tmp_path)

    with pytest.raises(ValueError, match="load.cir has no output"):
        read_chain([files["load"], files["series"], files["load"]])
    with pytest.raises(ValueError, match="across.cir is the last of the chain"):
        read_chain([files["series"], files["across"]])


def test_chain_by_the_names_of_its_stages_among_the_components(tmp_path, monkeypatch):
    (tmp_path / "afe").mkdir()
    files = _chain_files(tmp_path / "afe")
    monkeypatch.setenv("RASER_COMPONENT_PATH", str(tmp_path))

    chain = named_chain("across+series+series+load")

    assert chain == read_chain(
        [files["across"], files["series"], files["series"], files["load"]]
    )


def test_noiseless_resistor_loads_the_circuit_and_adds_no_noise(tmp_path):
    # 50 Ohm without noise across the line, then the 50 Ohm load at 300.15 K:
    # the load alone makes the noise, halved by the two in parallel
    path = tmp_path / "quiet.cir"
    path.write_text(
        ".subckt quiet in out\nR1 in 0 50 noisy=0\nR2 in out 1u\n.ends quiet\n"
    )
    load = {
        "ports": {"in": "a"},
        "elements": {"R1": {"between": ["a", "0"], "ohm": 50.0}},
    }
    stage = read_subcircuit(path)

    _, density = output_noise_spectrum(
        {"stages": {"quiet": stage}, "load": load},
        planar_circuit("top", 1e-12),
        1e3,
        1e6,
    )

    assert stage["elements"]["R1"] == {
        "between": ["in", "0"],
        "ohm": 50.0,
        "noiseless": True,
    }
    thermal = np.sqrt(4 * 1.380649e-23 * 300.15 * 50.0)
    assert density[0] == pytest.approx(thermal / 2, rel=1e-3)


@pytest.mark.parametrize(("frequency_hz", "gain_db"), [(100e6, 40.0), (2e9, 37.0)])
def test_broad_band_cividec_has_the_gain_its_maker_gives(frequency_hz, gain_db):
    # behind a source of 50 Ohm, on a 50 Ohm load, as Gali52 above: 40 dB,
    # 3 dB less at the 2 GHz of its bandwidth
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
            "BroadBandCividec": read_subcircuit(
                component_path("afe", "BroadBandCividec.cir")
            ),
        },
        "load": load,
    }
    dt = 1 / frequency_hz / 100
    times = (np.arange(3000) + 0.5) * dt
    sine = np.sin(2 * np.pi * frequency_hz * times)

    voltage = solve(chain, ["top"], dt, [1e-6 * sine], planar_circuit("top", 1e-15))

    settled = voltage[0][2000:]
    amplitude = (settled.max() - settled.min()) / 2
    assert 20 * np.log10(amplitude / 25e-6) == pytest.approx(gain_db, abs=0.25)
    if frequency_hz == 100e6:
        # it does not invert
        assert np.mean(settled * sine[2000:]) > 0.45 * amplitude


def test_broad_band_cividec_has_the_input_noise_its_maker_gives():
    # with nothing at its input: 0.4 uA rms, through the 50 Ohm of the input
    # and the gain of 100
    chain = named_chain("BroadBandCividec+Termination50")

    frequencies, density = output_noise_spectrum(
        chain, planar_circuit("top", 1e-18), 1e3, 1e12
    )

    power = density[0] ** 2
    rms = np.sqrt(np.sum((power[1:] + power[:-1]) / 2 * np.diff(frequencies)))
    assert rms / (50.0 * 100.0) == pytest.approx(0.4e-6, rel=0.08)


@pytest.mark.parametrize("sensor_pf", [1e-6, 20.0])
def test_charge_sensitive_cremat_has_the_step_its_maker_gives(sensor_pf):
    # -1 fC, on a 50 Ohm load: a step of half the 1.4 V/pC of the unloaded
    # output, upwards, at 90 percent after 3 ns + 0.22 ns per pF
    chain = named_chain("ChargeSensitiveCremat+Termination50")
    dt = 20e-12
    times = (np.arange(3000) + 0.5) * dt
    current = np.zeros(times.size)
    current[50] = -1e-15 / dt

    voltage = solve(
        chain, ["top"], dt, [current], planar_circuit("top", sensor_pf * 1e-12)
    )[0]

    assert voltage[-1] == pytest.approx(0.7e-3, rel=0.02)
    to_90_percent = np.interp(0.9, voltage / voltage[-1], times) - times[50]
    assert to_90_percent == pytest.approx(3e-9 + 0.22e-9 * sensor_pf, abs=0.15e-9)


def test_charge_sensitive_cremat_has_the_noise_slope_its_maker_gives():
    # as the maker measures it: behind a Gaussian shaping of 1 us, here a
    # differentiation and four integrations of 2.35 us FWHM; 3.8 electrons
    # per pF, between 50 and 100 pF where the capacitance alone counts
    chain = named_chain("ChargeSensitiveCremat+Termination50")
    shaping_s = 2.35e-6 / 4.755
    # the peak a step of 1 leaves behind the shaping: 4^4 exp(-4) / 4!
    electron_v = 0.7e-3 / 1e-15 * 1.602176634e-19 * 256 * np.exp(-4) / 24

    def electrons(sensor_f):
        frequencies, density = output_noise_spectrum(
            chain, planar_circuit("top", sensor_f), 1e1, 1e10
        )
        omega = 2 * np.pi * frequencies * shaping_s
        power = density[0] ** 2 * omega**2 / (1 + omega**2) ** 5
        rms = np.sqrt(np.sum((power[1:] + power[:-1]) / 2 * np.diff(frequencies)))
        return rms / electron_v

    assert (electrons(100e-12) - electrons(50e-12)) / 50 == pytest.approx(3.8, rel=0.05)
