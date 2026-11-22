import hashlib

import numpy as np
import pytest

from raser.stages.analysis.collection import efficiency_spread
from raser.stages.analysis.collection import event_efficiencies
from raser.stages.analysis.timing import point_tables
from raser.core.reconstruction.event_table import EventTable
from raser.core.reconstruction.event_table import write_event_table
from raser.core.current.currents import EventCurrents
from raser.core.current.currents import append_currents
from raser.core.deposit.deposits import Deposits
from raser.core.deposit.deposits import EventDeposits
from raser.core.deposit.deposits import write_deposits

E = 1.602176634e-19


def _nodes(folder, index):
    """The node of each slice of job `index` of the experiment folder
    `folder`: twelve hex digits, a different one for each file."""
    return {
        name: hashlib.sha1(f"{folder}/{index}/{name}".encode()).hexdigest()[:12]
        for name in ("deposit", "current", "readout", "reconstruction")
    }


def _of(folder, index):
    """Job `index` of the experiment folder `folder`, as lifecycle hands it
    out: the experiment folder and the node of each of its slices."""
    return (folder, _nodes(folder, index))


def _slice(folder, index, name):
    """The file of the slice `name` of job `index` of the experiment folder
    `folder`: in the node of the slice."""
    path = folder / "nodes" / name / _nodes(folder, index)[name] / f"{name}.h5"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _job(folder, index, efficiencies):
    """A job whose events have 1000 pairs each and these efficiencies, and
    a reconstruction table of the same events."""
    folder.mkdir(parents=True, exist_ok=True)
    for number, efficiency in enumerate(efficiencies):
        charge = np.array([-1000 * E * efficiency])
        append_currents(
            _slice(folder, index, "current"),
            ["top"],
            1.0e-11,
            EventCurrents(number, 0.0, np.zeros((1, 2)), charge, 1000.0),
        )
    table = EventTable(["top"], 3.0e-3, 5.0e-3, (0.5,), ["falling"], {"event": np.arange(len(efficiencies))})
    write_event_table(_slice(folder, index, "reconstruction"), table)


def point_efficiency(jobs):
    return efficiency_spread(event_efficiencies(point_tables(jobs)))


def _empty_job(folder, index, events):
    folder.mkdir(parents=True, exist_ok=True)
    write_deposits(str(_slice(folder, index, "deposit")), Deposits(50, None, None, events))


def test_point_takes_the_events_of_all_its_jobs(tmp_path) -> None:
    first, second = tmp_path / "seed_1", tmp_path / "seed_2"
    _job(first, 0, [0.8, 1.0])
    _job(first, 1, [0.9])
    _job(second, 0, [0.9, 0.9])
    _job(second, 3, [5.0])  # not among the finished jobs
    _empty_job(second, 1, [])

    result = point_efficiency([_of(first, 0), _of(first, 1), _of(second, 0), _of(second, 1)])

    values = [0.8, 1.0, 0.9, 0.9, 0.9]
    assert result["events"] == 5
    assert result["mean"] == pytest.approx(0.9)
    assert result["spread"] == pytest.approx(np.std(values, ddof=1))
    assert result["mean_error"] == pytest.approx(np.std(values, ddof=1) / np.sqrt(5))


def test_job_with_events_but_no_reconstruction_file_is_an_error(tmp_path) -> None:
    folder = tmp_path / "seed_1"
    _job(folder, 0, [0.8, 1.0])
    event = EventDeposits(4, ["Device"], [0.0], [0.0], [1.0], [0.0], [0.1], [1000.0])
    _empty_job(folder, 1, [event])

    with pytest.raises(FileNotFoundError, match="the job recorded 1 events but left no reconstruction file"):
        point_efficiency([_of(folder, 0), _of(folder, 1)])
