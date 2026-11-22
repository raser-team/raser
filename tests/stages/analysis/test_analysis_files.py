import pytest

from raser.stages.analysis.files import job_file
from raser.stages.analysis.files import slice_file
from raser.core.deposit.deposits import Deposits
from raser.core.deposit.deposits import EventDeposits
from raser.core.deposit.deposits import write_deposits

NODES = {
    "deposit": "0123456789ab",
    "current": "ba9876543210",
    "readout": "a1b2c3d4e5f6",
    "reconstruction": "f6e5d4c3b2a1",
}


def test_slice_file_is_in_the_node_of_its_slice_in_the_experiment_folder(tmp_path) -> None:
    for name, node in NODES.items():
        assert slice_file(tmp_path, NODES, name) == tmp_path / "nodes" / name / node / f"{name}.h5"


def test_job_without_events_is_known_from_its_deposits(tmp_path) -> None:
    deposits = slice_file(tmp_path, NODES, "deposit")
    deposits.parent.mkdir(parents=True)
    write_deposits(str(deposits), Deposits(50, {}, "any", None, []))

    assert job_file(tmp_path, NODES, "readout") is None


def test_job_with_events_but_without_a_file_is_an_error(tmp_path) -> None:
    deposits = slice_file(tmp_path, NODES, "deposit")
    deposits.parent.mkdir(parents=True)
    event = EventDeposits(4, ["Device"], [0.0], [0.0], [1.0], [0.0], [0.1], [1000.0])
    write_deposits(str(deposits), Deposits(50, {}, "any", None, [event]))

    with pytest.raises(FileNotFoundError, match="the job recorded 1 events but left no readout file"):
        job_file(tmp_path, NODES, "readout")


def test_job_file_is_the_file_of_the_slice_when_it_exists(tmp_path) -> None:
    path = slice_file(tmp_path, NODES, "readout")
    path.parent.mkdir(parents=True)
    path.touch()

    assert job_file(tmp_path, NODES, "readout") == path
