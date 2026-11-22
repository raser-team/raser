import h5py
import numpy as np
import pytest

from raser.core.readout.waveforms import EventWaveforms
from raser.core.readout.waveforms import append_waveforms
from raser.core.readout.waveforms import read_waveforms


def test_waveforms_file_returns_each_event_with_its_own_bins(tmp_path):
    electrodes = ["left", "right"]
    first = EventWaveforms(
        event=3,
        t0=-1.25e-9,
        voltage=np.array([[0.0, 1.0e-3, 2.0e-3], [0.0, -1.0e-3, -2.0e-3]]),
    )
    second = EventWaveforms(
        event=7,
        t0=-1.0e-9,
        voltage=np.array(
            [[3.0e-3, 4.0e-3, 5.0e-3, 6.0e-3], [7.0e-3, 8.0e-3, 9.0e-3, 1.0e-2]]
        ),
    )
    path = tmp_path / "waveforms.h5"

    append_waveforms(
        path, electrodes, 5.0e-12, 2.0e-11, first, pulse_edge=["falling"] * 2
    )
    append_waveforms(
        path, electrodes, 5.0e-12, 2.0e-11, second, pulse_edge=["falling"] * 2
    )
    waveforms = read_waveforms(path)

    assert waveforms.electrodes == electrodes
    assert waveforms.dt == 5.0e-12
    assert [record.event for record in waveforms.events] == [3, 7]
    assert [record.t0 for record in waveforms.events] == [-1.25e-9, -1.0e-9]
    for read, written in zip(waveforms.events, (first, second), strict=True):
        np.testing.assert_array_equal(read.voltage, written.voltage)


def test_waveforms_file_refuses_an_event_of_other_electrodes(tmp_path):
    record = EventWaveforms(1, 0.0, np.zeros((2, 3)))
    path = tmp_path / "waveforms.h5"
    append_waveforms(path, ["left", "right"], 5.0e-12, 2.0e-11, record)

    with pytest.raises(ValueError, match="holds waveforms of electrodes"):
        append_waveforms(path, ["right", "left"], 5.0e-12, 2.0e-11, record)


def test_each_event_keeps_the_electrodes_it_has_a_signal_on(tmp_path):
    electrodes = ["s1", "s2", "s3", "s4", "s5"]
    events = [
        EventWaveforms(
            0, 0.0, np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]), ["s4", "s2"]
        ),
        EventWaveforms(1, 1e-9, np.zeros((0, 2)), []),
        EventWaveforms(2, 2e-9, np.array([[7.0, 8.0]]), ["s5"]),
    ]
    path = tmp_path / "waveforms.h5"
    for record in events:
        append_waveforms(
            path, electrodes, 5.0e-12, 2.0e-11, record, pulse_edge=["rising"] * 5
        )

    read = read_waveforms(path).events

    assert [record.electrodes for record in read] == [["s4", "s2"], [], ["s5"]]
    assert [record.t0 for record in read] == [0.0, 1e-9, 2e-9]
    for got, written in zip(read, events, strict=True):
        np.testing.assert_array_equal(got.voltage, written.voltage)
    with pytest.raises(ValueError, match="not each once of the electrodes"):
        append_waveforms(
            path,
            electrodes,
            5.0e-12,
            2.0e-11,
            EventWaveforms(3, 0.0, np.zeros((1, 2)), ["s9"]),
        )


def test_file_of_an_older_layout_is_refused_and_left_as_it_is(tmp_path):
    # the layout before the stored electrodes: a column of voltage for each
    path = tmp_path / "readout_0.h5"
    with h5py.File(path, "w") as file:
        file.attrs.create("electrodes", ["top"], dtype=h5py.string_dtype())
        file.attrs["dt"] = 5.0e-12
        file.attrs.create("pulse_edge", ["falling"], dtype=h5py.string_dtype())
        for name in ("event", "t0", "count"):
            file.create_dataset(name, data=np.zeros(1), maxshape=(None,))
        file.create_dataset("voltage", data=np.zeros((3, 1)), maxshape=(None, 1))
    record = EventWaveforms(1, 0.0, np.zeros((1, 3)))

    with pytest.raises(ValueError, match="older layout.*run the readout again"):
        append_waveforms(
            path, ["top"], 5.0e-12, 2.0e-11, record, pulse_edge=["falling"]
        )
    with pytest.raises(ValueError, match="older layout.*run the readout again"):
        read_waveforms(path)
    with h5py.File(path) as file:
        assert file["event"].shape == (1,)


def test_waveforms_file_returns_the_length_of_its_part_before_the_currents(tmp_path):
    path = tmp_path / "waveforms.h5"
    record = EventWaveforms(1, 0.0, np.zeros((1, 3)))
    append_waveforms(path, ["top"], 5.0e-12, 6.0e-11, record, pulse_edge=["falling"])

    assert read_waveforms(path).pre_window == 6.0e-11


def test_waveforms_file_refuses_an_event_of_another_pre_window(tmp_path):
    path = tmp_path / "waveforms.h5"
    record = EventWaveforms(1, 0.0, np.zeros((1, 3)))
    append_waveforms(path, ["top"], 5.0e-12, 6.0e-11, record, pulse_edge=["falling"])

    with pytest.raises(
        ValueError, match="with dt 5e-12 s and pre_window 6e-11 s, not of"
    ):
        append_waveforms(path, ["top"], 5.0e-12, 7.0e-11, record)


def test_waveforms_file_without_pre_window_is_not_read(tmp_path):
    path = tmp_path / "waveforms.h5"
    record = EventWaveforms(1, 0.0, np.zeros((1, 3)))
    append_waveforms(path, ["top"], 5.0e-12, 6.0e-11, record, pulse_edge=["falling"])
    with h5py.File(path, "a") as file:
        del file.attrs["pre_window"]

    with pytest.raises(ValueError) as error:
        read_waveforms(path)
    assert str(error.value) == (
        f"{path} has no pre_window: the readout of this version did not write "
        "it; run the readout again"
    )
