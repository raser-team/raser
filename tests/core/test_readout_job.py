import json

import numpy as np
import pytest

from raser.core.current.currents import EventCurrents, append_currents
from raser.core.device.build_device import Detector, device_file
from raser.core.field.circuit_parameters import device_circuit
from raser.core.field.device_circuit import planar_circuit, side_by_side
from raser.core.readout import job
from raser.core.readout.circuit import named_chain
from raser.core.readout.job import LOWEST_NOISE_HZ, noise_spectra, write_waveforms
from raser.core.readout.waveforms import read_circuit_values, read_waveforms

pytestmark = pytest.mark.ngspice

DT_S = 5e-12
# a wire on a 50 Ohm load: the 10 pF device sees the load
CHAIN = {
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


def _step_event(event, t0, bins, current_a):
    """A current that starts at t = 0 and stays, on bins that start at t0."""
    times = t0 + (np.arange(bins) + 0.5) * DT_S
    current = np.where(times > 0, current_a, 0.0)[None, :]
    return times, EventCurrents(event, t0, current, np.zeros(1), 0.0)


def test_each_event_of_the_currents_file_gets_its_waveform(tmp_path):
    currents_path = tmp_path / "currents_0.h5"
    waveforms_path = tmp_path / "waveforms_0.h5"
    first_times, first = _step_event(4, -1.0e-9, 1000, 1e-6)
    second_times, second = _step_event(9, -0.5e-9, 600, -3e-6)
    append_currents(currents_path, ["top"], DT_S, first)
    append_currents(currents_path, ["top"], DT_S, second)
    circuit = planar_circuit("top", 10e-12)

    values = {"junction_capacitance": {"farad": 10e-12, "from": "device file"}}

    write_waveforms(currents_path, waveforms_path, CHAIN, circuit, None)
    assert read_circuit_values(waveforms_path) is None
    # a second start of the job replaces the file instead of adding to it
    write_waveforms(currents_path, waveforms_path, CHAIN, circuit, None, values)
    waveforms = read_waveforms(waveforms_path)

    assert read_circuit_values(waveforms_path) == values

    assert waveforms.electrodes == ["top"]
    assert waveforms.dt == DT_S
    assert [record.event for record in waveforms.events] == [4, 9]
    assert [record.t0 for record in waveforms.events] == [-1.0e-9, -0.5e-9]
    for record, times, current_a in (
        (waveforms.events[0], first_times, 1e-6),
        (waveforms.events[1], second_times, -3e-6),
    ):
        after = np.clip(times, 0, None)
        expected = current_a * 50.0 * (1 - np.exp(-after / (50.0 * 10e-12)))
        off_the_jump = (times < 0) | (times > DT_S)
        assert record.voltage[0][off_the_jump] == pytest.approx(
            expected[off_the_jump], abs=2e-7
        )


def test_noise_of_the_circuit_is_added_to_every_event(tmp_path):
    # no current at all: what is left is the noise of the 50 Ohm load on the
    # 10 pF device, whose rms is sqrt(k T / C) at 300.15 K
    currents_path = tmp_path / "currents_0.h5"
    quiet = EventCurrents(0, 0.0, np.zeros((1, 2000)), np.zeros(1), 0.0)
    for event in range(10):
        quiet.event = event
        append_currents(currents_path, ["top"], DT_S, quiet)
    circuit = planar_circuit("top", 10e-12)

    def noise(seed):
        path = tmp_path / f"waveforms_{seed}.h5"
        write_waveforms(currents_path, path, CHAIN, circuit, seed)
        return np.array([record.voltage[0] for record in read_waveforms(path).events])

    first = noise(3)

    assert first.std() == pytest.approx(
        np.sqrt(1.380649e-23 * 300.15 / 10e-12), rel=0.15
    )
    # each event has its own noise, the seed fixes all of it
    assert abs(np.mean(first[0] * first[1])) < 0.2 * first.var()
    np.testing.assert_array_equal(noise(3), first)
    assert not np.array_equal(noise(4), first)


def _quiet_events(path, electrodes, events, bins):
    count = len(electrodes)
    quiet = EventCurrents(0, 0.0, np.zeros((count, bins)), np.zeros(count), 0.0)
    for event in range(events):
        quiet.event = event
        append_currents(path, electrodes, DT_S, quiet)


def test_outputs_that_differ_each_have_the_noise_of_their_own_circuit(tmp_path):
    currents_path = tmp_path / "currents_0.h5"
    _quiet_events(currents_path, ["small", "large"], 10, 2000)
    circuit = side_by_side(
        [planar_circuit("small", 10e-12), planar_circuit("large", 40e-12)]
    )

    path = tmp_path / "waveforms_0.h5"
    write_waveforms(currents_path, path, CHAIN, circuit, 5)
    voltage = np.array([record.voltage for record in read_waveforms(path).events])

    k_t = 1.380649e-23 * 300.15
    assert voltage[:, 0].std() == pytest.approx(np.sqrt(k_t / 10e-12), rel=0.15)
    assert voltage[:, 1].std() == pytest.approx(np.sqrt(k_t / 40e-12), rel=0.15)


def _row_of_six():
    """Six strips 1 cm long of ITk-Si-strip, coupled to the strips two
    places away: 1 pF in all, 0.6 pF to the nearest two, 0.2 pF to the next
    two, per cm. The circuit of each strip, and the groups of alike ones."""
    content = json.loads(device_file("ITk-Si-strip").read_text(encoding="utf-8"))
    my_d = Detector("ITk-Si-strip", {**content, "read_ele_num": 6, "l_y": 10000})
    row = {
        "unit": "F/cm",
        "of": "top",
        "total": 1.0e-12,
        "to": {"neighbour1": 0.6e-12, "neighbour2": 0.2e-12, "bot": 0.2e-12},
        "neighbours_coupled": 2,
    }
    names = [f"top{k}" for k in range(1, 7)]
    circuit, _ = device_circuit(my_d, names, row=row)
    return names, circuit


@pytest.mark.parametrize(
    "chain", [CHAIN, named_chain("SantaCruz+Gali52+Termination50")]
)
def test_each_strip_of_a_row_has_the_noise_of_its_own_place(chain, monkeypatch):
    # the strips at the ends and next to them lack neighbours: three
    # spectra, each that of every strip of its group
    names, circuit = _row_of_six()
    analysed = []
    spectrum = job.output_noise_spectrum

    def counted(chain, circuit, lowest_hz, highest_hz, outputs=None):
        analysed.append(outputs)
        return spectrum(chain, circuit, lowest_hz, highest_hz, outputs)

    monkeypatch.setattr(job, "output_noise_spectrum", counted)

    frequencies, shared = noise_spectra(chain, circuit, 1e3, 1e11)
    _, own = spectrum(chain, circuit, 1e3, 1e11)

    assert circuit.alike == (("top1", "top6"), ("top2", "top5"), ("top3", "top4"))
    assert len(analysed[0]) == 3
    np.testing.assert_allclose(shared, own, rtol=1e-6)
    # the ends do differ from the middle
    assert not np.allclose(own[0], own[2], rtol=1e-3, atol=0)


def test_every_strip_draws_noise_of_its_own(tmp_path):
    names, circuit = _row_of_six()
    currents_path = tmp_path / "currents_0.h5"
    _quiet_events(currents_path, names, 40, 400)

    path = tmp_path / "waveforms_0.h5"
    write_waveforms(currents_path, path, CHAIN, circuit, 5)
    voltage = np.array([record.voltage for record in read_waveforms(path).events])

    # at one time, across the 40 events: no two strips alike
    at_once = voltage[:, :, 200]
    correlation = np.corrcoef(at_once.T)
    assert np.max(np.abs(correlation - np.eye(6))) < 0.5
    frequencies, densities = noise_spectra(CHAIN, circuit, LOWEST_NOISE_HZ, 0.5 / DT_S)
    power = np.sum(
        (densities[:, 1:] ** 2 + densities[:, :-1] ** 2) / 2 * np.diff(frequencies),
        axis=1,
    )
    assert voltage.std(axis=(0, 2)) == pytest.approx(np.sqrt(power), rel=0.2)
