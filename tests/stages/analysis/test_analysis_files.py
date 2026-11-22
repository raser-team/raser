import json

from raser.stages.analysis.files import job_file
from raser.stages.analysis.files import slice_file
from raser.core.deposit.deposits import Deposits
from raser.core.deposit.deposits import write_deposits


def _mark(folder, index, name, node):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "batch").mkdir(exist_ok=True)
    (folder / "batch" / f"{name}_{index}.done").write_text(json.dumps({"node": node}))


def test_slice_file_is_in_the_node_that_the_mark_of_the_point_that_holds_the_slice_names(tmp_path) -> None:
    # two amplifiers on the same events: the second point reads the deposits
    # and the currents of the first, the electronics scan as a whole reads
    # nothing above the experiment
    folder = tmp_path / "amplifier=B" / "seed_7"
    folder.mkdir(parents=True)
    held = {"deposit": "", "current": "amplifier=A", "readout": "amplifier=B"}
    (folder / "run.json").write_text(json.dumps({"point": "amplifier=B", "held_in": held}))

    _mark(tmp_path / "seed_7", 3, "deposit", "0123456789ab")
    _mark(tmp_path / "amplifier=A" / "seed_7", 3, "current", "ba9876543210")
    _mark(folder, 3, "readout", "a1b2c3d4e5f6")

    assert slice_file(folder, 3, "deposit") == tmp_path / "nodes" / "deposit" / "0123456789ab" / "deposit.h5"
    assert slice_file(folder, 3, "current") == tmp_path / "nodes" / "current" / "ba9876543210" / "current.h5"
    assert slice_file(folder, 3, "readout") == tmp_path / "nodes" / "readout" / "a1b2c3d4e5f6" / "readout.h5"


def test_job_without_events_is_known_from_the_deposits_in_the_node_of_the_point_that_holds_them(tmp_path) -> None:
    folder = tmp_path / "amplifier=B" / "seed_7"
    folder.mkdir(parents=True)
    held = {"deposit": "", "current": "", "readout": "amplifier=B"}
    (folder / "run.json").write_text(json.dumps({"point": "amplifier=B", "held_in": held}))
    _mark(tmp_path / "seed_7", 3, "deposit", "0123456789ab")
    (folder / "batch").mkdir(parents=True, exist_ok=True)
    (folder / "batch" / "readout_3.done").touch()  # the mark of a slice that did not run: no node
    deposits = tmp_path / "nodes" / "deposit" / "0123456789ab" / "deposit.h5"
    deposits.parent.mkdir(parents=True)
    write_deposits(str(deposits), Deposits(50, None, None, []))

    assert job_file(folder, 3, "readout") is None
