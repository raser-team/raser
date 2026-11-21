import numpy as np
import pytest

from raser.core.current.currents import EventCurrents
from raser.core.current.currents import append_currents
from raser.core.frontend.job import write_waveforms
from raser.core.frontend.planar_sensor import planar_sensor
from raser.core.frontend.waveforms import read_sensor_values
from raser.core.frontend.waveforms import read_waveforms

pytestmark = pytest.mark.ngspice

DT_S = 5e-12
# a wire on a 50 Ohm load: the 10 pF sensor sees the load
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
    sensor = planar_sensor("top", 10e-12)

    values = {"junction_capacitance": {"farad": 10e-12, "from": "device file"}}

    write_waveforms(currents_path, waveforms_path, CHAIN, sensor, None)
    assert read_sensor_values(waveforms_path) is None
    # a second start of the job replaces the file instead of adding to it
    write_waveforms(currents_path, waveforms_path, CHAIN, sensor, None, values)
    waveforms = read_waveforms(waveforms_path)

    assert read_sensor_values(waveforms_path) == values

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
    # 10 pF sensor, whose rms is sqrt(k T / C) at 300.15 K
    currents_path = tmp_path / "currents_0.h5"
    quiet = EventCurrents(0, 0.0, np.zeros((1, 2000)), np.zeros(1), 0.0)
    for event in range(10):
        quiet.event = event
        append_currents(currents_path, ["top"], DT_S, quiet)
    sensor = planar_sensor("top", 10e-12)

    def noise(seed):
        path = tmp_path / f"waveforms_{seed}.h5"
        write_waveforms(currents_path, path, CHAIN, sensor, seed)
        return np.array([record.voltage[0] for record in read_waveforms(path).events])

    first = noise(3)

    assert first.std() == pytest.approx(
        np.sqrt(1.380649e-23 * 300.15 / 10e-12), rel=0.15
    )
    # each event has its own noise, the seed fixes all of it
    assert abs(np.mean(first[0] * first[1])) < 0.2 * first.var()
    np.testing.assert_array_equal(noise(3), first)
    assert not np.array_equal(noise(4), first)
