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

    append_waveforms(path, electrodes, 5.0e-12, first)
    append_waveforms(path, electrodes, 5.0e-12, second)
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
    append_waveforms(path, ["left", "right"], 5.0e-12, record)

    with pytest.raises(ValueError, match="holds waveforms of electrodes"):
        append_waveforms(path, ["right", "left"], 5.0e-12, record)
