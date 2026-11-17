from __future__ import annotations

from pathlib import Path

from raser.core.deposit.deposits import Deposits
from raser.core.deposit.deposits import EventDeposits
from raser.core.deposit.deposits import write_deposits
from raser.stages import current
from raser.stages import readout


def _job(tmp_path: Path) -> dict:
    batch = tmp_path / "batch"
    batch.mkdir()
    names = ("deposit", "current.A", "current.B", "readout.A", "readout.B")
    return {"job_index": 0, "_slice_batch_paths": dict.fromkeys(names, str(batch))}


def test_a_position_with_no_deposit_in_the_job_leaves_no_currents(tmp_path: Path) -> None:
    kwargs = _job(tmp_path)
    in_a = EventDeposits(0, ["A"], [1.0], [1.0], [1.0], [0.0], [0.1], pairs=[10.0])
    write_deposits(str(tmp_path / "batch" / "deposit_0.h5"), Deposits(1, None, None, [in_a]))

    assert current.currents(kwargs, "B") == {"events": 0}
    assert not (tmp_path / "batch" / "current.B_0.h5").exists()


def test_a_position_that_left_no_currents_leaves_no_readout(tmp_path: Path) -> None:
    kwargs = _job(tmp_path)

    assert readout.waveforms(kwargs, "B") == {"events": 0}
    assert not (tmp_path / "batch" / "readout.B_0.h5").exists()
