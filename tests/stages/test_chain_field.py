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
    # the job of each point runs here, not in a process of its own
    monkeypatch.setattr(
        workflow, "_own_process", lambda flow, kwargs, words: workflow._run_job(flow, {**kwargs, "job_dir": words[-1]})
    )
    ran: list[str] = []
    seeds: list[tuple[str, str, int]] = []  # slice, point folder, the seed it ran with

    def note(options, name):
        ran.append(name)
        seeds.append((name, Path(options["_run_path"]).parent.name, options["seed"]))
    started: list[float] = []
    state = {"ready": True}

    def shared_start(kwargs, options, files):
        started.append(options["voltage"])

    shared = Shared(
        ready=lambda options, files: Path("field") if state["ready"] else None, start=shared_start
    )
    pieces = tuple(
        replace(piece, run=lambda options, name=piece.name: note(options, name), shared=shared if piece.shared else None)
        for piece in chain.SLICES
    )
    toy = Workflow(name="signal", keys=chain.KEYS, in_file=chain.IN_FILE, slices=pieces)
    return {"workflow": toy, "ran": ran, "started": started, "state": state, "root": tmp_path / "dev" / "signal", "seeds": seeds}


def _kwargs(**given: Any) -> dict[str, Any]:
    kwargs: dict[str, Any] = {"det_name": "dev", "jobs": None, "batch": False, "mem": 1, "seed": 1}
    kwargs.update(dry_run=False, scan=[], same_seeds=False, _entry_command_prefix=("signal",))
    return {**kwargs, **given}


def _held_in(root: Path, point: str) -> dict[str, str]:
    return json.loads((root / point / "seed_1" / "run.json").read_text())["held_in"]


def test_a_scanned_bias_gives_every_point_its_own_deposits(experiment: dict[str, Any]) -> None:
    execute(experiment["workflow"], _kwargs(scan=["voltage=100,300"]))

    for point in ("voltage_100", "voltage_300"):
        assert _held_in(experiment["root"], point) == dict.fromkeys(("deposits", "field", "currents", "waveforms"), point)
    assert experiment["ran"].count("deposits") == 2
    # the points draw other numbers in the same job
    drawn = {point: seed for name, point, seed in experiment["seeds"] if name == "deposits"}
    assert drawn["voltage_100"] != drawn["voltage_300"]


def test_with_same_seeds_the_points_of_a_bias_scan_share_one_run_of_the_deposits(
    experiment: dict[str, Any],
) -> None:
    execute(experiment["workflow"], _kwargs(scan=["voltage=100,300"], same_seeds=True))

    for point in ("voltage_100", "voltage_300"):
        held_in = _held_in(experiment["root"], point)
        assert held_in["deposits"] == ""
        assert [held_in[name] for name in ("field", "currents", "waveforms")] == [point] * 3
    assert [experiment["ran"].count(name) for name in ("deposits", "field", "currents")] == [1, 2, 2]
    # and the same numbers in the same job
    drawn = {point: seed for name, point, seed in experiment["seeds"] if name == "currents"}
    assert drawn["voltage_100"] == drawn["voltage_300"]


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


def _solved_field(project: Path, device: dict[str, Any], point: str = "") -> Path:
    """A field of `device` solved at 200 V, as `raser field` records it, in
    the folder of a point of the field experiment."""
    folder = project / "field" / point
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


def test_of_the_fields_at_a_flux_the_one_of_this_device_is_taken(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RASER_PROJECT_PATH", str(tmp_path))
    device = device_json("HPK-Si-PiN")
    device["bias"]["voltage"] = 200.0
    doped = json.loads(json.dumps(device))
    doped["doping"]["Acceptors"] = "1e13"
    plain = _solved_field(tmp_path, device)
    other = _solved_field(tmp_path, doped, "doping.Acceptors_1e13")
    options = {"voltage": 200.0, "irradiation": None}

    assert field.ready(options, {"device": device}) == plain
    assert field.ready(options, {"device": doped}) == other


def test_a_change_of_the_device_that_the_field_does_not_read_takes_the_field_there_is(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RASER_PROJECT_PATH", str(tmp_path))
    device = device_json("HPK-Si-PiN")
    device["bias"]["voltage"] = 200.0
    folder = _solved_field(tmp_path, device)

    longer = {**device, "l_y": 2 * device["l_y"]}  # not read by this field
    assert field.ready({"voltage": 200.0, "irradiation": None, "device.l_y": longer["l_y"]}, {"device": longer}) == folder


def test_the_field_is_solved_for_the_device_as_the_point_changed_it(monkeypatch: pytest.MonkeyPatch) -> None:
    asked: list[list[str]] = []
    monkeypatch.setattr(field, "execute", lambda flow, kwargs: asked.append(kwargs["scan"]))
    device = device_json("HPK-Si-PiN")
    device["bias"]["voltage"] = 300.0
    device["doping"]["Acceptors"] = "1e13"
    options = {"voltage": 300.0, "irradiation": None, "device.doping.Acceptors": "1e13", "device.bias.voltage": 300.0}

    field.start({"batch": False, "mem": 1}, options, {"device": device})

    assert asked == [['device.doping.Acceptors="1e13"']]


def test_a_shared_slice_made_here_that_is_still_not_ready_stops_the_command(
    experiment: dict[str, Any],
) -> None:
    experiment["state"]["ready"] = False

    with pytest.raises(RuntimeError, match="still not ready"):
        execute(experiment["workflow"], _kwargs())


def test_a_field_that_another_command_is_solving_makes_the_points_wait(
    experiment: dict[str, Any],
) -> None:
    experiment["state"]["ready"] = False

    def solving_elsewhere(kwargs, options, files):
        raise workflow.Running("work/dev/field is run by another process now")

    pieces = tuple(
        replace(piece, shared=Shared(ready=piece.shared.ready, start=solving_elsewhere)) if piece.shared else piece
        for piece in experiment["workflow"].slices
    )

    with pytest.raises(SystemExit, match="wait for field, shared with other experiments"):
        execute(replace(experiment["workflow"], slices=pieces), _kwargs())
    assert experiment["ran"] == []
