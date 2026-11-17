import json

import numpy as np
import pytest

from raser.stages.analysis.collection import efficiency_spread
from raser.stages.analysis.collection import event_efficiencies
from raser.stages.analysis.timing import point_tables
from raser.core.readout.waveforms import EventWaveforms
from raser.core.readout.waveforms import append_waveforms
from raser.core.current.currents import EventCurrents
from raser.core.current.currents import append_currents
from raser.core.deposit.deposits import Deposits
from raser.core.deposit.deposits import EventDeposits
from raser.core.deposit.deposits import write_deposits

E = 1.602176634e-19


def _alone(folder):
    """The seed folder of an experiment without points: it holds its slices."""
    folder.mkdir(parents=True, exist_ok=True)
    held = {"deposit": "", "current": "", "readout": ""}
    (folder / "run.json").write_text(json.dumps({"point": "", "held_in": held}))


def _job(folder, index, efficiencies):
    """A job whose events have 1000 pairs each and these efficiencies, and
    a waveform of a pulse of 10 mV."""
    _alone(folder)
    batch = folder / "batch"
    batch.mkdir(parents=True, exist_ok=True)
    events = []
    for number, efficiency in enumerate(efficiencies):
        charge = np.array([-1000 * E * efficiency])
        append_currents(
            batch / f"current_{index}.h5",
            ["top"],
            1.0e-11,
            EventCurrents(number, 0.0, np.zeros((1, 2)), charge, 1000.0),
        )
        samples = np.concatenate([np.zeros(200), [0.0, -5.0e-3, -10.0e-3, -5.0e-3, 0.0]])
        append_waveforms(batch / f"readout_{index}.h5", ["top"], 1.0e-9, EventWaveforms(number, 0.0, np.array([samples])))
        events.append(EventDeposits(number, ["Device"], [0.0], [0.0], [1.0], [0.0], [0.1], [1000.0]))
    write_deposits(str(batch / f"deposit_{index}.h5"), Deposits(50, None, None, events))


def point_efficiency(jobs):
    return efficiency_spread(event_efficiencies(point_tables(jobs, 3.0e-3, 5.0e-3)))


def _empty_job(folder, index, events):
    _alone(folder)
    batch = folder / "batch"
    batch.mkdir(parents=True, exist_ok=True)
    write_deposits(str(batch / f"deposit_{index}.h5"), Deposits(50, None, None, events))


def test_point_takes_the_events_of_all_its_jobs(tmp_path) -> None:
    first, second = tmp_path / "seed_1", tmp_path / "seed_2"
    _job(first, 0, [0.8, 1.0])
    _job(first, 1, [0.9])
    _job(second, 0, [0.9, 0.9])
    _job(second, 3, [5.0])  # not among the finished jobs
    _empty_job(second, 1, [])

    result = point_efficiency([(first, 0), (first, 1), (second, 0), (second, 1)])

    values = [0.8, 1.0, 0.9, 0.9, 0.9]
    assert result["events"] == 5
    assert result["mean"] == pytest.approx(0.9)
    assert result["spread"] == pytest.approx(np.std(values, ddof=1))
    assert result["mean_error"] == pytest.approx(np.std(values, ddof=1) / np.sqrt(5))


def test_job_with_events_but_no_readout_file_is_an_error(tmp_path) -> None:
    folder = tmp_path / "seed_1"
    _job(folder, 0, [0.8, 1.0])
    event = EventDeposits(4, ["Device"], [0.0], [0.0], [1.0], [0.0], [0.1], [1000.0])
    _empty_job(folder, 1, [event])

    with pytest.raises(FileNotFoundError, match="job 1 recorded 1 events but left no readout file"):
        point_efficiency([(folder, 0), (folder, 1)])
