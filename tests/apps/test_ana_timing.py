import json

import numpy as np
import pytest

from raser.apps.ana.timing import event_times
from raser.core.frontend.waveforms import EventWaveforms
from raser.core.frontend.waveforms import append_waveforms
from raser.core.interaction.deposits import Deposits
from raser.core.interaction.deposits import write_deposits

# a negative triangle [V]: 2 mV per bin up to 10 mV in bin 6, then down again
TRIANGLE = 1.0e-3 * np.array([0.0, 0, -2, -4, -6, -8, -10, -8, -6, -4, -2, 0, 0])
DT = 1.0e-9  # with a 3 mV threshold the arrival is 2.5 ns and the half height 4 ns after t0


def _alone(folder):
    """The seed folder of an experiment without points: it holds its slices."""
    folder.mkdir(parents=True, exist_ok=True)
    held = {"deposits": "", "currents": "", "waveforms": ""}
    (folder / "run.json").write_text(json.dumps({"point": "", "held_in": held}))


def _job(folder, index, events, electrodes=("top",)):
    """A job with one event per (t0, scale): the triangle, scaled, starting at t0."""
    _alone(folder)
    batch = folder / "batch"
    batch.mkdir(parents=True, exist_ok=True)
    for number, (t0, scale) in enumerate(events):
        voltage = np.array([scale * TRIANGLE] * len(electrodes))
        append_waveforms(
            batch / f"waveforms_{index}.h5", list(electrodes), DT, EventWaveforms(number, t0, voltage)
        )


def test_point_takes_the_quantities_of_the_events_above_the_amplitude_threshold(tmp_path) -> None:
    first, second = tmp_path / "seed_1", tmp_path / "seed_2"
    _job(first, 0, [(0.0, 1.0), (1.0e-10, 1.0)])
    _job(first, 1, [(2.0e-10, 0.4)])  # 4 mV, below the amplitude threshold
    _job(second, 0, [(-1.0e-10, 2.0)])  # 20 mV: crosses 3 mV one bin earlier
    _job(second, 2, [(5.0e-9, 1.0)])  # not among the finished jobs
    (second / "batch").mkdir(exist_ok=True)
    write_deposits(str(second / "batch" / "deposits_1.h5"), Deposits(50, None, None, []))

    count, times = event_times([(first, 0), (first, 1), (second, 0), (second, 1)], 3.0e-3, 5.0e-3)

    assert count == 4
    assert times["ToA"] == pytest.approx(np.array([2.5e-9, 2.6e-9, 1.4e-9]))
    assert times["ToT"] == pytest.approx(np.array([8.0e-9, 8.0e-9, 10.0e-9]))
    assert times["amplitude"] == pytest.approx(np.array([10.0e-3, 10.0e-3, 20.0e-3]))
    starts = np.array([0.0, 1.0e-10, -1.0e-10])
    # the triangle is symmetric about the centre of bin 6
    assert times["CoG"] == pytest.approx(starts + 6.5e-9)
    # the edge rises by a fifth of the amplitude per ns from 1.5 ns after t0
    for percent in (10, 20, 30, 40, 50, 60, 70, 80, 90):
        assert times[f"CFD{percent}"] == pytest.approx(starts + 1.5e-9 + percent * 5.0e-11)


def test_several_electrodes_are_refused(tmp_path) -> None:
    _job(tmp_path, 0, [(0.0, 1.0)], electrodes=("left", "right"))

    with pytest.raises(NotImplementedError, match="2 electrodes"):
        event_times([(tmp_path, 0)], 3.0e-3, 5.0e-3)
