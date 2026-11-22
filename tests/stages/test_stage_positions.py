from __future__ import annotations

from pathlib import Path

import pytest

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
    write_deposits(str(tmp_path / "batch" / "deposit_0.h5"), Deposits(1, {}, "any", None, [in_a]))

    assert current.currents(kwargs, "B") == {"events": 0}
    assert not (tmp_path / "batch" / "current.B_0.h5").exists()


def test_a_position_that_left_no_currents_leaves_no_readout(tmp_path: Path) -> None:
    kwargs = _job(tmp_path)

    assert readout.waveforms(kwargs, "B") == {"events": 0}
    assert not (tmp_path / "batch" / "readout.B_0.h5").exists()


def test_a_position_with_a_deposit_drifts_its_own_and_its_readout_reads_its_currents(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    kwargs = {**_job(tmp_path), "det_name": "D", "_files": {"device": {}}, "plots": 0, "amplifier": "amp"}
    in_a = EventDeposits(0, ["A"], [1.0], [1.0], [1.0], [0.0], [0.1], pairs=[10.0])
    write_deposits(str(tmp_path / "batch" / "deposit_0.h5"), Deposits(1, {}, "any", None, [in_a]))
    drifted: list[tuple[str, str, object]] = []
    read: list[tuple[str, str]] = []
    device = type("Device", (), {"read_out_contact": [], "read_ele_num": 1, "device_dict": {}, "irradiation_flux": 0, "voltage": 1})()
    monkeypatch.setattr(current.bdv, "Detector", lambda name, files: device)
    monkeypatch.setattr(current, "solved", lambda my_d, kwargs: None)

    def drift(deposits, out, *args, **options) -> None:
        drifted.append((deposits, out, options.get("detector")))
        Path(out).touch()

    monkeypatch.setattr(current, "write_induced_currents", drift)
    monkeypatch.setattr(readout.bdv, "Detector", lambda name, files: device)
    monkeypatch.setattr(readout, "electrode_names", lambda contacts, count: [])
    monkeypatch.setattr(readout, "solved_field", lambda my_d, voltage, flux: None)
    monkeypatch.setattr(readout, "field_circuit", lambda folder, my_d: (None, None, None))
    monkeypatch.setattr(readout, "device_circuit", lambda my_d, names, *a, **k: (type("Circuit", (), {"outputs": []})(), None))
    monkeypatch.setattr(readout, "pulse_edges", lambda my_d, chain, outputs: [])
    monkeypatch.setattr(readout, "named_chain", lambda name: None)
    monkeypatch.setattr(readout, "write_waveforms", lambda currents, out, *args, **options: read.append((currents, out)))
    batch = tmp_path / "batch"

    assert current.currents(kwargs, "A") is None
    assert readout.waveforms(kwargs, "A") is None

    assert drifted == [(str(batch / "deposit_0.h5"), str(batch / "current.A_0.h5"), "A")]
    assert read == [(str(batch / "current.A_0.h5"), str(batch / "readout.A_0.h5"))]
