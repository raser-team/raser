import json

import numpy as np
import pytest

from raser.stages.analysis.timing import event_times
from raser.stages.analysis.timing import point_resolution
from raser.core.readout.waveforms import EventWaveforms
from raser.core.readout.waveforms import append_waveforms
from raser.core.deposit.deposits import Deposits
from raser.core.deposit.deposits import EventDeposits
from raser.core.deposit.deposits import write_deposits

# a negative triangle [V]: 2 mV per bin up to 10 mV in bin 6, then down again
TRIANGLE = 1.0e-3 * np.array([0.0, 0, -2, -4, -6, -8, -10, -8, -6, -4, -2, 0, 0])
DT = 1.0e-9  # with a 3 mV threshold the arrival is 3 ns and the half height 4 ns after t0
BEFORE = 200  # bins before the triangle
OFFSET = 2.0e-3  # of the baseline [V]


def _alone(folder):
    """The seed folder of an experiment without points: it holds its slices."""
    folder.mkdir(parents=True, exist_ok=True)
    held = {"deposit": "", "current": "", "readout": ""}
    (folder / "run.json").write_text(json.dumps({"point": "", "held_in": held}))


def _job(folder, index, events, electrodes=("top",), truths=None):
    """A job with one event per (t0, scale): the triangle, scaled, starting at
    t0, on a baseline 2 mV above zero that starts 200 bins earlier. The last
    bin of the second event of a job is 12 mV above the baseline. Event n of
    job i has the Geant4 number 1000 i + n and two deposits, the earlier one
    (n + 1) ps before t0, or at truths[n]."""
    _alone(folder)
    batch = folder / "batch"
    batch.mkdir(parents=True, exist_ok=True)
    deposits = []
    for number, (t0, scale) in enumerate(events):
        earliest = t0 - (number + 1) * 1.0e-12 if truths is None else truths[number]
        deposits.append(
            EventDeposits(
                1000 * index + number, ["Device"] * 2, [0.0] * 2, [0.0] * 2, [1.0, 2.0],
                [earliest + 5.0e-12, earliest], [0.1] * 2, [1000.0] * 2,
            )
        )
        samples = OFFSET + np.concatenate([np.zeros(BEFORE), scale * TRIANGLE])
        if number == 1:
            samples[-1] += 12.0e-3
        voltage = np.array([samples] * len(electrodes))
        append_waveforms(
            batch / f"readout_{index}.h5",
            list(electrodes),
            DT,
            EventWaveforms(1000 * index + number, t0 - BEFORE * DT, voltage),
            pulse_edge=["rising"] * len(electrodes),
        )
    write_deposits(str(batch / f"deposit_{index}.h5"), Deposits(50, None, None, deposits))


def test_point_takes_the_quantities_of_the_events_above_the_amplitude_threshold(tmp_path) -> None:
    first, second = tmp_path / "seed_1", tmp_path / "seed_2"
    _job(first, 0, [(0.0, 1.0), (1.0e-10, 1.0)])
    _job(first, 1, [(2.0e-10, 0.4)])  # 4 mV, below the amplitude threshold
    _job(second, 0, [(-1.0e-10, 2.0)])  # 20 mV: crosses 3 mV three quarters of a bin earlier
    _job(second, 2, [(5.0e-9, 1.0)])  # not among the finished jobs
    write_deposits(str(second / "batch" / "deposit_1.h5"), Deposits(50, None, None, []))

    count, polarity, times = event_times([(first, 0), (first, 1), (second, 0), (second, 1)], 3.0e-3, 5.0e-3)

    assert count == 4
    # the 12 mV above the baseline are not the pulse of the second event
    assert polarity == -1.0
    # the event below the amplitude threshold is the only one of the second job; the last is event 0 of the third
    assert list(times["job"]) == [0, 0, 2]
    assert list(times["event"]) == [0, 1, 0]
    assert times["ToA"] == pytest.approx(np.array([3.0e-9, 3.1e-9, 2.15e-9]))
    assert times["ToT"] == pytest.approx(np.array([7.0e-9, 7.0e-9, 8.5e-9]))
    assert times["amplitude"] == pytest.approx(np.array([10.0e-3, 10.0e-3, 20.0e-3]))
    assert times["baseline"] == pytest.approx(np.full(3, OFFSET))
    starts = np.array([0.0, 1.0e-10, -1.0e-10])
    assert times["truth"] == pytest.approx(starts - np.array([1.0e-12, 2.0e-12, 1.0e-12]))
    # the triangle is symmetric about the centre of bin 6
    assert times["CoG"] == pytest.approx(starts + 6.5e-9)
    # the edge rises by a fifth of the amplitude per ns from 1.5 ns after t0
    for percent in (10, 20, 30, 40, 50, 60, 70, 80, 90):
        assert times[f"CFD{percent}"] == pytest.approx(starts + 1.5e-9 + percent * 5.0e-11)


def test_several_electrodes_are_refused(tmp_path) -> None:
    _job(tmp_path, 0, [(0.0, 1.0)], electrodes=("left", "right"))

    with pytest.raises(NotImplementedError, match="2 electrodes"):
        event_times([(tmp_path, 0)], 3.0e-3, 5.0e-3)


def test_event_that_is_not_among_the_deposits_is_an_error(tmp_path) -> None:
    _job(tmp_path, 0, [(0.0, 1.0)])
    _job(tmp_path, 1, [(0.0, 1.0)])
    batch = tmp_path / "batch"
    (batch / "deposit_1.h5").write_bytes((batch / "deposit_0.h5").read_bytes())

    with pytest.raises(ValueError, match="event 1000 is not among the deposits"):
        event_times([(tmp_path, 0), (tmp_path, 1)], 3.0e-3, 5.0e-3)


def test_resolution_is_the_width_of_time_minus_truth(tmp_path) -> None:
    # the primaries start over 1 ns; the pulse follows its primary within 30 ps
    rng = np.random.default_rng(4)
    truths = rng.normal(0.0, 1.0e-9, 600)
    starts = truths + rng.normal(0.0, 3.0e-11, 600)
    _job(tmp_path, 0, [(t0, 1.0) for t0 in starts[:300]], truths=truths[:300])
    # 4 mV, below the amplitude threshold
    _job(tmp_path, 1, [(t0, 0.4) for t0 in starts[300:]], truths=truths[300:])

    result = point_resolution([(tmp_path, 0), (tmp_path, 1)], 3.0e-3, 5.0e-3)

    assert (result["events"], result["selected"], result["polarity"]) == (600, 300, -1.0)
    half = result["times"]["CFD50"]
    assert (half["events"], half["missing"]) == (300, 0)
    # the half height is 4 ns after the start of the triangle
    assert half["mean"] == pytest.approx(4.0e-9, abs=5 * half["mean_error"])
    assert half["mean_error"] < 5.0e-12
    assert half["sigma"] == pytest.approx(3.0e-11, abs=5 * half["sigma_error"])
    assert half["sigma_error"] < 5.0e-12
    assert set(result["times"]) == {"ToA", "CoG"} | {f"CFD{k}0" for k in range(1, 10)}


def test_selected_event_without_a_time_is_counted_as_missing(tmp_path) -> None:
    rng = np.random.default_rng(5)
    truths = rng.normal(0.0, 1.0e-9, 100)
    _job(tmp_path, 0, [(t0, 1.0) for t0 in truths + rng.normal(0.0, 3.0e-11, 100)], truths=truths)
    # in one more event the pulse is in the first bin: nothing before it to cross
    samples = OFFSET + np.concatenate([[-10.0e-3], np.zeros(BEFORE + 12)])
    append_waveforms(
        tmp_path / "batch" / "readout_0.h5",
        ["top"],
        DT,
        EventWaveforms(0, 0.0, np.array([samples])),
        pulse_edge=["rising"],
    )

    result = point_resolution([(tmp_path, 0)], 3.0e-3, 5.0e-3)

    assert (result["events"], result["selected"]) == (101, 101)
    half = result["times"]["CFD50"]
    assert (half["events"], half["missing"]) == (100, 1)
    assert half["sigma"] == pytest.approx(3.0e-11, abs=5 * half["sigma_error"])
