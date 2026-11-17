from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from raser.core.device.build_device import device_json
from raser.core.field.solved import DEFAULT_MODE
from raser.lifecycle import jobs
from raser.lifecycle import workflow
from raser.lifecycle.slices import Shared
from raser.lifecycle.workflow import Workflow
from raser.lifecycle.workflow import execute
from raser.stages import chain
from raser.stages import field


@pytest.fixture
def experiment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """A device "dev" biased at 200 V in a project of its own; the slices
    of the chain only note that they ran, and no generator is seeded."""
    monkeypatch.setenv("RASER_PROJECT_PATH", str(tmp_path / "dev"))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(workflow, "_commit", lambda: "abc")
    monkeypatch.setattr(workflow, "device_json", lambda name: {"det_name": name, "bias": {"voltage": 200.0}})
    monkeypatch.setitem(sys.modules, "raser.core.seeding", SimpleNamespace(seed_generators=lambda seed: None))
    ran: list[str] = []
    started: list[float] = []
    state = {"ready": True}

    def shared_start(kwargs, options, files):
        started.append(options["voltage"])

    shared = Shared(
        ready=lambda options, files: Path("field") if state["ready"] else None, start=shared_start
    )
    pieces = tuple(
        replace(piece, run=lambda options, name=piece.name: ran.append(name), shared=shared if piece.shared else None)
        for piece in chain.SLICES
    )
    toy = Workflow(name="signal", keys=chain.KEYS, in_file=chain.IN_FILE, slices=pieces)
    return {"workflow": toy, "ran": ran, "started": started, "state": state}


def _kwargs(**given: Any) -> dict[str, Any]:
    kwargs: dict[str, Any] = {"det_name": "dev", "jobs": None, "batch": False, "mem": 1, "seed": 1}
    kwargs.update(dry_run=False, scan=[], same_seeds=False, _entry_command_prefix=("signal",))
    return {**kwargs, **given}


def test_another_bias_runs_the_field_and_what_follows_it_but_not_the_deposits(
    experiment: dict[str, Any],
) -> None:
    execute(experiment["workflow"], _kwargs())
    experiment["ran"].clear()

    execute(experiment["workflow"], _kwargs(voltage=100.0))

    assert experiment["ran"] == ["field", "currents", "waveforms"]


def test_a_field_not_ready_is_started_once_for_the_points_that_share_it_and_their_jobs_wait(
    experiment: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(jobs, "run_indexed_jobs", lambda *args, **kwargs: pytest.fail("submitted"))
    experiment["state"]["ready"] = False
    scan = ["voltage=100,300", "amplifier=a,b"]

    with pytest.raises(SystemExit, match="wait for field, shared with other experiments"):
        execute(experiment["workflow"], _kwargs(batch=True, jobs=1, scan=scan))

    assert sorted(experiment["started"]) == [100.0, 300.0]
    assert experiment["ran"] == []


def _solved_field(project: Path, device: dict[str, Any]) -> Path:
    """A field of `device` solved at 200 V, as `raser field` records it."""
    folder = project / "field"
    folder.mkdir(parents=True)
    record = {
        "options": {"irradiation_flux": None, "mode": DEFAULT_MODE},
        "files": {"device": device},
        "read": {"attributes": {}, "keys": {"doping": {"Acceptors": device["doping"]["Acceptors"]}}, "files": {}},
        "solved": {"potential": [0.0, 200.0], "weighting": [200.0]},
    }
    (folder / "run.json").write_text(json.dumps(record))
    return folder


def test_the_field_is_ready_only_as_raser_field_would_leave_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RASER_PROJECT_PATH", str(tmp_path))
    device = device_json("HPK-Si-PiN")
    device["bias"]["voltage"] = 200.0
    folder = _solved_field(tmp_path, device)
    options = {"voltage": 200.0, "irradiation": None}

    assert field.ready(options, {"device": device}) == folder

    doped = json.loads(json.dumps(device))
    doped["doping"]["Acceptors"] = "1e13"
    assert field.ready(options, {"device": doped}) is None  # another device
    settled = {**device, "field": {"solver": {"saved_voltage_interval": 50}}}
    assert field.ready(options, {"device": settled}) is None  # other "field" settings
    lower = json.loads(json.dumps(device))
    lower["bias"]["voltage"] = 100.0
    assert field.ready(options, {"device": lower}) is None  # not solved at this bias
    assert field.ready({**options, "irradiation": 1e14}, {"device": device}) is None  # another flux
