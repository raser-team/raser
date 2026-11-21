import h5py
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


def _events_with_quiet_electrodes():
    first = np.zeros((5, 3))
    first[0] = [1.0e-6, 2.0e-6, 3.0e-6]
    first[3] = [-4.0e-6, -5.0e-6, -6.0e-6]
    second = np.zeros((5, 4))
    second[2] = [7.0e-6, 8.0e-6, 9.0e-6, 1.0e-5]
    return (
        EventCurrents(3, 0.0, first, np.array([3.0e-17, 0.0, 0.0, -7.5e-17, 0.0]), 96.5),
        EventCurrents(7, 1.0e-9, second, np.array([0.0, 0.0, 1.7e-16, 0.0, 0.0]), 1800.0),
    )


def test_currents_file_returns_no_current_on_the_quiet_electrodes(tmp_path) -> None:
    written = _events_with_quiet_electrodes()
    path = tmp_path / "currents.h5"

    for record in written:
        append_currents(path, list("abcde"), 5.0e-12, record)
    events = read_currents(path).events

    for read, record in zip(events, written, strict=True):
        np.testing.assert_array_equal(read.current, record.current)
        np.testing.assert_array_equal(read.charge, record.charge)


def test_currents_file_stores_only_the_electrodes_with_current(tmp_path) -> None:
    path = tmp_path / "currents.h5"

    for record in _events_with_quiet_electrodes():
        append_currents(path, list("abcde"), 5.0e-12, record)

    with h5py.File(path, "r") as file:
        assert file["current"].shape == (2 * 3 + 1 * 4,)


def test_currents_file_refuses_an_event_of_other_electrodes(tmp_path) -> None:
    record = EventCurrents(1, 0.0, np.zeros((2, 3)), np.zeros(2), 0.0)
    path = tmp_path / "currents.h5"
    append_currents(path, ["left", "right"], 5.0e-12, record)

    with pytest.raises(ValueError, match="holds currents of electrodes"):
        append_currents(path, ["right", "left"], 5.0e-12, record)


def test_currents_file_keeps_the_sensitive_pairs_of_each_event(tmp_path) -> None:
    path = tmp_path / "currents.h5"
    for number, sensitive in ((3, 90.5), (7, 1750.0)):
        append_currents(path, ["a"], 5.0e-12, EventCurrents(number, 0.0, np.ones((1, 2)), np.zeros(1), 2000.0, sensitive))

    assert [record.sensitive_pairs for record in read_currents(path).events] == [90.5, 1750.0]


def test_currents_file_refuses_an_event_without_sensitive_pairs_among_those_with(tmp_path) -> None:
    path = tmp_path / "currents.h5"
    append_currents(path, ["a"], 5.0e-12, EventCurrents(3, 0.0, np.ones((1, 2)), np.zeros(1), 2000.0, 90.5))

    with pytest.raises(ValueError, match="holds sensitive_pairs"):
        append_currents(path, ["a"], 5.0e-12, EventCurrents(7, 0.0, np.ones((1, 2)), np.zeros(1), 2000.0))


def test_currents_file_keeps_the_carriers_that_found_no_field_of_each_event(tmp_path) -> None:
    path = tmp_path / "currents.h5"
    for number, lost in ((3, 0.0), (7, 41.5)):
        append_currents(
            path, ["a"], 5.0e-12, EventCurrents(number, 0.0, np.ones((1, 2)), np.zeros(1), 2000.0, 1990.0, lost)
        )

    assert [record.carriers_without_field for record in read_currents(path).events] == [0.0, 41.5]
