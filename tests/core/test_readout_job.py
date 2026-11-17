import json

import numpy as np
import pytest

from raser.core.current.currents import EventCurrents, append_currents
from raser.core.device.build_device import Detector, device_file
from raser.core.field.circuit_parameters import device_circuit
from raser.core.field.circuit_parameters import part_of_row
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

    write_waveforms(
        currents_path, waveforms_path, CHAIN, circuit, None, pulse_edge=["rising"]
    )
    assert read_circuit_values(waveforms_path) is None
    # a second start of the job replaces the file instead of adding to it
    write_waveforms(
        currents_path, waveforms_path, CHAIN, circuit, None, values, ["rising"]
    )
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


def _pulsed_events(path, electrodes, events, bins):
    """Events with 1 fC on every electrode in the first bins, so that every
    output is stored."""
    count = len(electrodes)
    current = np.zeros((count, bins))
    current[:, :4] = 1e-15 / (4 * DT_S)
    for event in range(events):
        append_currents(
            path,
            electrodes,
            DT_S,
            EventCurrents(event, 0.0, current, current.sum(axis=1) * DT_S, 0.0),
        )


def _noise(tmp_path, currents_path, circuit, seed, edges):
    """The noise of every event, shape (events, outputs, bins): what the seed
    adds to the waveforms without noise."""

    def voltages(seed):
        path = tmp_path / f"waveforms_{seed}.h5"
        write_waveforms(currents_path, path, CHAIN, circuit, seed, pulse_edge=edges)
        return np.array([record.voltage for record in read_waveforms(path).events])

    return voltages(seed) - voltages(None)


def test_noise_of_the_circuit_is_added_to_every_event(tmp_path):
    # the noise of the 50 Ohm load on the 10 pF device, whose rms is
    # sqrt(k T / C) at 300.15 K
    currents_path = tmp_path / "currents_0.h5"
    _pulsed_events(currents_path, ["top"], 10, 2000)
    circuit = planar_circuit("top", 10e-12)

    def noise(seed):
        return _noise(tmp_path, currents_path, circuit, seed, ["rising"])[:, 0]

    first = noise(3)

    assert first.std() == pytest.approx(
        np.sqrt(1.380649e-23 * 300.15 / 10e-12), rel=0.15
    )
    # each event has its own noise, the seed fixes all of it
    assert abs(np.mean(first[0] * first[1])) < 0.2 * first.var()
    np.testing.assert_array_equal(noise(3), first)
    assert not np.array_equal(noise(4), first)


def test_outputs_that_differ_each_have_the_noise_of_their_own_circuit(tmp_path):
    currents_path = tmp_path / "currents_0.h5"
    _pulsed_events(currents_path, ["small", "large"], 10, 2000)
    circuit = side_by_side(
        [planar_circuit("small", 10e-12), planar_circuit("large", 40e-12)]
    )

    voltage = _noise(tmp_path, currents_path, circuit, 5, ["rising"] * 2)

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
    _pulsed_events(currents_path, names, 40, 400)

    voltage = _noise(tmp_path, currents_path, circuit, 5, ["rising"] * 6)

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


def _row_of(count):
    """A row of `count` strips 1 cm long of ITk-Si-strip, coupled one place
    away: 1 pF in all, 0.6 pF to the nearest two, per cm."""
    content = json.loads(device_file("ITk-Si-strip").read_text(encoding="utf-8"))
    my_d = Detector("ITk-Si-strip", {**content, "read_ele_num": count, "l_y": 10000})
    row = {
        "unit": "F/cm",
        "of": "top",
        "total": 1.0e-12,
        "to": {"neighbour1": 0.6e-12, "bot": 0.4e-12},
        "neighbours_coupled": 1,
    }
    return my_d, [f"top{k}" for k in range(1, count + 1)], row


def test_part_of_a_row_is_the_strips_hit_and_its_margin_as_far_as_the_row_goes():
    my_d, names, row = _row_of(15)

    assert list(part_of_row(my_d, names, ["top8"], 2, row=row).outputs) == names[5:10]
    # two strips hit, one near an end, named in any order: up to the end,
    # and all between
    assert (
        list(part_of_row(my_d, names, ["top10", "top2"], 2, row=row).outputs)
        == (names[0:12])
    )


def test_row_holds_in_each_event_only_the_strips_the_charge_reaches(tmp_path):
    # 1 fC on the middle one of 41 strips, then an event without current;
    # the part grows from one strip on each side until what reaches its ends
    # is below a thousandth
    my_d, names, row = _row_of(41)
    circuit, _ = device_circuit(my_d, names, row=row)
    current = np.zeros((41, 600))
    current[20, 20:40] = 1e-15 / (20 * DT_S)
    currents_path = tmp_path / "currents_0.h5"
    for number, event_current in ((0, current), (1, np.zeros_like(current))):
        append_currents(
            currents_path,
            names,
            DT_S,
            EventCurrents(
                number, 0.0, event_current, event_current.sum(axis=1) * DT_S, 0.0
            ),
        )

    def read(path, seed=None, **part):
        write_waveforms(
            currents_path,
            path,
            CHAIN,
            circuit,
            seed,
            pulse_edge=["rising"] * 41,
            **part,
        )
        return read_waveforms(path).events

    def part_of(hit, margin):
        return part_of_row(my_d, names, hit, margin, row=row)

    whole = read(tmp_path / "whole.h5")[0]
    hit, quiet = read(tmp_path / "part.h5", part_of=part_of)

    # solved whole or in a part, the strips stored are the same: those the
    # charge reaches by a thousandth of the strip hit, not the whole row
    assert hit.electrodes == whole.electrodes
    first, last = names.index(hit.electrodes[0]), names.index(hit.electrodes[-1])
    assert hit.electrodes == names[first : last + 1]
    assert first < 19 and last > 21 and last - first + 1 < 41
    # each strip of it as in the whole row
    peak = np.abs(whole.voltage).max()
    assert np.abs(hit.voltage - whole.voltage).max() < 1e-3 * peak
    # the event without current has no waveforms, not even noise
    assert quiet.electrodes == [] and quiet.voltage.shape == (0, 600)
    noisy, quiet = read(tmp_path / "noisy.h5", seed=3, part_of=part_of)
    assert noisy.electrodes == hit.electrodes and quiet.electrodes == []
    # every strip stored has its noise
    assert np.all((noisy.voltage - hit.voltage).std(axis=1) > 0.1 * peak / 50)


def test_currents_in_another_order_than_the_row_are_solved_where_they_are(tmp_path):
    # the file names the strips from the last to the first; 1 fC on top25,
    # the 17th in the file
    my_d, names, row = _row_of(41)
    circuit, _ = device_circuit(my_d, names, row=row)
    in_file = names[::-1]
    current = np.zeros((41, 400))
    current[in_file.index("top25"), 20:40] = 1e-15 / (20 * DT_S)
    currents_path = tmp_path / "currents_0.h5"
    append_currents(
        currents_path,
        in_file,
        DT_S,
        EventCurrents(0, 0.0, current, current.sum(axis=1) * DT_S, 0.0),
    )

    asked = []

    def part_of(hit, margin):
        asked.append(list(hit))
        return part_of_row(my_d, names, hit, margin, row=row)

    path = tmp_path / "readout_0.h5"
    write_waveforms(
        currents_path,
        path,
        CHAIN,
        circuit,
        None,
        pulse_edge=["rising"] * 41,
        part_of=part_of,
    )
    event = read_waveforms(path).events[0]

    # the part is asked around the strip by its name, wherever the file has it
    assert asked[0] == ["top25"]
    assert "top25" in event.electrodes and len(event.electrodes) < 41
    place = np.argmax(np.abs(event.voltage).max(axis=1))
    assert event.electrodes[place] == "top25"


def _stored(tmp_path, my_d, names, row, current, part=True):
    """The strips stored of one event with `current`, solved in parts or
    whole, the widest part solved, and their voltages."""
    circuit, _ = device_circuit(my_d, names, row=row)
    currents_path = tmp_path / "currents_0.h5"
    currents_path.unlink(missing_ok=True)
    append_currents(
        currents_path,
        names,
        DT_S,
        EventCurrents(0, 0.0, current, current.sum(axis=1) * DT_S, 0.0),
    )
    widest = []

    def part_of(hit, margin):
        circuit = part_of_row(my_d, names, hit, margin, row=row)
        widest.append(len(circuit.outputs))
        return circuit

    path = tmp_path / "readout_0.h5"
    path.unlink(missing_ok=True)
    write_waveforms(
        currents_path,
        path,
        CHAIN,
        circuit,
        None,
        pulse_edge=["rising"] * len(names),
        part_of=part_of if part else None,
    )
    event = read_waveforms(path).events[0]
    return event.electrodes, max(widest, default=len(names)), event.voltage


def test_strips_coupled_two_places_away_are_reached_though_the_next_are_not(tmp_path):
    # the nearest strips barely coupled, those two places away strongly: the
    # charge skips a strip, which a part judged by its ends would miss
    content = json.loads(device_file("ITk-Si-strip").read_text(encoding="utf-8"))
    my_d = Detector("ITk-Si-strip", {**content, "read_ele_num": 21, "l_y": 10000})
    names = [f"top{k}" for k in range(1, 22)]
    row = {
        "unit": "F/cm",
        "of": "top",
        "total": 1.0e-12,
        "to": {"neighbour1": 1e-17, "neighbour2": 0.8e-12, "bot": 0.2e-12},
        "neighbours_coupled": 2,
    }
    current = np.zeros((21, 400))
    current[10, 20:40] = 1e-15 / (20 * DT_S)

    in_part, _, part = _stored(tmp_path, my_d, names, row, current)
    whole_names, _, whole = _stored(tmp_path, my_d, names, row, current, part=False)

    assert {"top9", "top13"} <= set(in_part)
    assert in_part == whole_names
    assert np.abs(part - whole).max() < 1e-3 * np.abs(whole).max()


def test_part_at_the_end_of_a_row_grows_only_inwards(tmp_path):
    # 1 fC on the first of 41 strips: the end of the row is no reason to
    # widen, and the part stays well short of the row
    my_d, names, row = _row_of(41)
    current = np.zeros((41, 400))
    current[0, 20:40] = 1e-15 / (20 * DT_S)

    in_part, widest, part = _stored(tmp_path, my_d, names, row, current)
    whole_names, _, whole = _stored(tmp_path, my_d, names, row, current, part=False)

    assert widest < 41
    assert in_part == whole_names and in_part[0] == "top1"
    assert np.abs(part - whole).max() < 1e-3 * np.abs(whole).max()


def test_quiet_strips_between_two_hits_are_not_stored(tmp_path):
    my_d, names, row = _row_of(41)
    current = np.zeros((41, 400))
    current[[5, 35], 20:40] = 1e-15 / (20 * DT_S)

    in_part, _, _ = _stored(tmp_path, my_d, names, row, current)

    assert {"top6", "top36"} <= set(in_part)
    assert "top21" not in in_part
