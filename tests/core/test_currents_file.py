import numpy as np
import pytest

from raser.core.current.currents import EventCurrents
from raser.core.current.currents import append_currents
from raser.core.current.currents import read_currents


def test_currents_file_returns_each_event_with_its_own_bins(tmp_path) -> None:
    electrodes = ["left", "right"]
    first = EventCurrents(
        event=3,
        t0=-1.25e-9,
        current=np.array([[0.0, 1.0e-6, 2.0e-6], [0.0, -1.0e-6, -2.0e-6]]),
        charge=np.array([1.5e-17, -1.5e-17]),
        pairs=96.5,
    )
    second = EventCurrents(
        event=7,
        t0=-1.0e-9,
        current=np.array([[3.0e-6, 4.0e-6, 5.0e-6, 6.0e-6], [7.0e-6, 8.0e-6, 9.0e-6, 1.0e-5]]),
        charge=np.array([9.0e-17, 1.7e-16]),
        pairs=1800.0,
    )
    path = tmp_path / "currents.h5"

    append_currents(path, electrodes, 5.0e-12, first)
    append_currents(path, electrodes, 5.0e-12, second)
    currents = read_currents(path)

    assert currents.electrodes == electrodes
    assert currents.dt == 5.0e-12
    assert [record.event for record in currents.events] == [3, 7]
    assert [record.t0 for record in currents.events] == [-1.25e-9, -1.0e-9]
    assert [record.pairs for record in currents.events] == [96.5, 1800.0]
    for read, written in zip(currents.events, (first, second), strict=True):
        np.testing.assert_array_equal(read.current, written.current)
        np.testing.assert_array_equal(read.charge, written.charge)


def test_currents_file_refuses_an_event_of_other_electrodes(tmp_path) -> None:
    record = EventCurrents(1, 0.0, np.zeros((2, 3)), np.zeros(2), 0.0)
    path = tmp_path / "currents.h5"
    append_currents(path, ["left", "right"], 5.0e-12, record)

    with pytest.raises(ValueError, match="holds currents of electrodes"):
        append_currents(path, ["right", "left"], 5.0e-12, record)
