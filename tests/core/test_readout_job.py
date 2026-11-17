import dataclasses

import numpy as np
import pytest

from raser.core.current.currents import EventCurrents
from raser.core.current.currents import append_currents
from raser.core.readout import job
from raser.core.readout.job import write_waveforms
from raser.core.field.device_circuit import planar_circuit
from raser.core.field.device_circuit import side_by_side
from raser.core.readout.waveforms import read_circuit_values
from raser.core.readout.waveforms import read_waveforms

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


def test_alike_outputs_share_one_spectrum_and_draw_their_own_noise(
    tmp_path, monkeypatch
):
    electrodes = [f"strip{k}" for k in range(5)]
    currents_path = tmp_path / "currents_0.h5"
    _quiet_events(currents_path, electrodes, 10, 2000)
    circuit = dataclasses.replace(
        side_by_side([planar_circuit(name, 10e-12) for name in electrodes]),
        outputs_alike=True,
    )
    analysed = []
    spectrum = job.output_noise_spectrum

    def counted(chain, circuit, lowest_hz, highest_hz, outputs=None):
        analysed.append(outputs)
        return spectrum(chain, circuit, lowest_hz, highest_hz, outputs)

    monkeypatch.setattr(job, "output_noise_spectrum", counted)

    path = tmp_path / "waveforms_0.h5"
    write_waveforms(currents_path, path, CHAIN, circuit, 5)
    voltage = np.array([record.voltage for record in read_waveforms(path).events])

    # the spectrum of the middle strip, once, for all five
    assert analysed == [["strip2"]]
    assert voltage.std(axis=(0, 2)) == pytest.approx(
        np.sqrt(1.380649e-23 * 300.15 / 10e-12), rel=0.15
    )
    # each strip its own noise
    assert abs(np.mean(voltage[:, 0] * voltage[:, 1])) < 0.2 * voltage.var()
