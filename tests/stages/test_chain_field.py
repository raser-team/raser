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
from raser.lifecycle.workflow import execute
from raser.stages import chain
from raser.stages import field
from raser_bench.signal import WORKFLOW


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
    state = {"ready": True, "stamp": "first solve"}

    def shared_start(kwargs, options, files):
        started.append(options["voltage"])

    shared = Shared(
        ready=lambda options, files: Path("field") if state["ready"] else None,
        start=shared_start,
        stamp=lambda options, files: state["stamp"] if state["ready"] else None,
    )
    pieces = tuple(
        replace(piece, run=lambda options, name=piece.name: note(options, name), shared=shared if piece.shared else None)
        for piece in chain.SLICES
    )
    toy = replace(WORKFLOW, slices=pieces, analysis=None)
    return {"workflow": toy, "ran": ran, "started": started, "state": state, "root": tmp_path / "dev" / "signal", "seeds": seeds}


def _kwargs(**given: Any) -> dict[str, Any]:
    kwargs: dict[str, Any] = {"det_name": "dev", "jobs": None, "batch": False, "mem": 1, "seed": 1}
    kwargs.update(dry_run=False, set=[], scan=[], same_seeds=False, _entry_command_prefix=("signal",))
    return {**kwargs, **given}


def _held_in(root: Path, point: str) -> dict[str, str]:
    return json.loads((root / point / "seed_1" / "run.json").read_text())["held_in"]


def test_a_field_solved_again_runs_what_reads_it_again_and_keeps_the_deposits(experiment: dict[str, Any]) -> None:
    execute(experiment["workflow"], _kwargs())
    experiment["ran"].clear()
    execute(experiment["workflow"], _kwargs())
    assert experiment["ran"] == []  # the same field: nothing to run

    experiment["state"]["stamp"] = "solved again"
    execute(experiment["workflow"], _kwargs())
    assert experiment["ran"] == ["field", "current", "readout", "reconstruction"]

    experiment["ran"].clear()
    execute(experiment["workflow"], _kwargs())
    assert experiment["ran"] == []


def test_a_field_made_by_the_command_is_recorded_as_made_and_the_next_command_runs_nothing(
    experiment: dict[str, Any],
) -> None:
    experiment["state"]["ready"] = False

    def solve(kwargs, options, files):
        experiment["state"]["ready"] = True

    pieces = tuple(
        replace(piece, shared=replace(piece.shared, start=solve)) if piece.shared else piece
        for piece in experiment["workflow"].slices
    )
    toy = replace(experiment["workflow"], slices=pieces)
    execute(toy, _kwargs())
    experiment["ran"].clear()

    execute(toy, _kwargs())

    assert experiment["ran"] == []


def test_a_threshold_is_not_scanned_and_another_one_reconstructs_the_same_waveforms(experiment: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="reconstruction.threshold is not scanned"):
        execute(experiment["workflow"], _kwargs(scan=["reconstruction.threshold=30,60"]))
    assert experiment["ran"] == []

    execute(experiment["workflow"], _kwargs(set=["reconstruction.threshold=30"]))
    experiment["ran"].clear()
    execute(experiment["workflow"], _kwargs(set=["reconstruction.threshold=60"]))

    assert experiment["ran"] == ["reconstruction"]  # the events are those that were measured


def test_another_sheet_resistance_runs_the_readout_and_what_follows_it_alone(experiment: dict[str, Any]) -> None:
    execute(experiment["workflow"], _kwargs())
    experiment["ran"].clear()

    execute(experiment["workflow"], _kwargs(set=["readout.sheet_resistance=1.0e5"]))

    assert experiment["ran"] == ["readout", "reconstruction"]


def test_a_scanned_bias_gives_every_point_its_own_deposits(experiment: dict[str, Any]) -> None:
    execute(experiment["workflow"], _kwargs(scan=["field.voltage=100,300"]))

    for point in ("voltage_100", "voltage_300"):
        assert _held_in(experiment["root"], point) == dict.fromkeys(("deposit", "field", "current", "readout", "reconstruction"), point)
    assert experiment["ran"].count("deposit") == 2
    # the points draw other numbers in the same job
    drawn = {point: seed for name, point, seed in experiment["seeds"] if name == "deposit"}
    assert drawn["voltage_100"] != drawn["voltage_300"]


def test_with_same_seeds_the_points_of_a_bias_scan_share_one_run_of_the_deposits(
    experiment: dict[str, Any],
) -> None:
    execute(experiment["workflow"], _kwargs(scan=["field.voltage=100,300"], same_seeds=True))

    for point in ("voltage_100", "voltage_300"):
        held_in = _held_in(experiment["root"], point)
        assert held_in["deposit"] == ""
        assert [held_in[name] for name in ("field", "current", "readout")] == [point] * 3
    assert [experiment["ran"].count(name) for name in ("deposit", "field", "current")] == [1, 2, 2]
    # and the same numbers in the same job
    drawn = {point: seed for name, point, seed in experiment["seeds"] if name == "current"}
    assert drawn["voltage_100"] == drawn["voltage_300"]


def test_another_bias_runs_the_field_and_what_follows_it_but_not_the_deposits(
    experiment: dict[str, Any],
) -> None:
    execute(experiment["workflow"], _kwargs())
    experiment["ran"].clear()

    execute(experiment["workflow"], _kwargs(set=["field.voltage=100.0"]))

    assert experiment["ran"] == ["field", "current", "readout", "reconstruction"]


def test_a_field_not_ready_is_started_once_for_the_points_that_share_it_and_their_jobs_wait(
    experiment: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(jobs, "run_indexed_jobs", lambda *args, **kwargs: pytest.fail("submitted"))
    experiment["state"]["ready"] = False
    scan = ["field.voltage=100,300", "readout.amplifier=a,b"]

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
    options = {"voltage": 200.0, "irradiation_flux": None}

    assert field.ready(options, {"device": device}) == folder

    doped = json.loads(json.dumps(device))
    doped["doping"]["Acceptors"] = "1e13"
    assert field.ready(options, {"device": doped}) is None  # another device
    settled = {**device, "field": {"solver": {"saved_voltage_interval": 50}}}
    assert field.ready(options, {"device": settled}) is None  # other "field" settings
    lower = json.loads(json.dumps(device))
    lower["bias"]["voltage"] = 100.0
    assert field.ready(options, {"device": lower}) is None  # not solved at this bias
    assert field.ready({**options, "irradiation_flux": 1e14}, {"device": device}) is None  # another flux


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
    options = {"voltage": 200.0, "irradiation_flux": None}

    assert field.ready(options, {"device": device}) == plain
    assert field.ready(options, {"device": doped}) == other


def test_the_stamp_of_a_field_changes_with_a_solve_of_it_and_not_with_one_more_bias(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RASER_PROJECT_PATH", str(tmp_path))
    device = device_json("HPK-Si-PiN")
    device["bias"]["voltage"] = 200.0
    folder = _solved_field(tmp_path, device)
    options = {"voltage": 200.0, "irradiation_flux": None}
    first = field.stamp(options, {"device": device})
    record = json.loads((folder / "run.json").read_text())

    record["solved"]["potential"].append(300.0)  # another experiment's bias
    (folder / "run.json").write_text(json.dumps(record))
    assert field.stamp(options, {"device": device}) == first

    record["commit"] = "def"  # solved again, by other code
    (folder / "run.json").write_text(json.dumps(record))
    assert field.stamp(options, {"device": device}) not in (first, None)


def test_a_change_of_the_device_that_the_field_does_not_read_takes_the_field_there_is(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RASER_PROJECT_PATH", str(tmp_path))
    device = device_json("HPK-Si-PiN")
    device["bias"]["voltage"] = 200.0
    folder = _solved_field(tmp_path, device)

    longer = {**device, "l_y": 2 * device["l_y"]}  # not read by this field
    assert field.ready({"voltage": 200.0, "irradiation_flux": None, "device.l_y": longer["l_y"]}, {"device": longer}) == folder


def test_the_field_is_solved_for_the_device_as_the_point_changed_it(monkeypatch: pytest.MonkeyPatch) -> None:
    asked: list[tuple[float, list[str], bool, int]] = []

    def execute(flow, kwargs, register) -> None:
        asked.append((kwargs["bias"], kwargs["scan"], register, kwargs["jobs"]))

    monkeypatch.setattr(field, "execute", execute)
    device = device_json("HPK-Si-PiN")
    device["bias"]["voltage"] = 300.0
    device["temperature"] = 280.0
    options = {"voltage": 300.0, "irradiation_flux": None, "device.temperature": 280.0, "device.bias.voltage": 300.0}

    field.start({"batch": False, "mem": 1}, options, {"device": device})

    # not one of the field's own scans, and solved in a process of its own
    assert asked == [(300.0, ["device.temperature=280.0"], False, 1)]


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


def test_a_field_started_for_an_experiment_hands_its_job_the_command_that_waits(monkeypatch: pytest.MonkeyPatch) -> None:
    handed: list[Any] = []
    monkeypatch.setattr(field, "execute", lambda flow, kwargs, register: handed.append(kwargs["_waiting"]))
    device = device_json("HPK-Si-PiN")
    waiting = {"command": ["-b", "signal", "HPK-Si-PiN"], "cwd": "/work", "seed_folder": "seed_1"}

    field.start({"batch": True, "mem": 1, "_waiting": waiting}, {"voltage": None, "irradiation_flux": None}, {"device": device})

    assert handed == [waiting]


def test_the_settings_of_a_field_command_are_its_linear_solver_and_the_content_of_its_tcad_file(tmp_path: Path) -> None:
    tdr = tmp_path / "device.tdr"
    tdr.write_bytes(b"one solution")
    plain = field.WORKFLOW.settings({"umf": False, "input": None})
    umf = field.WORKFLOW.settings({"umf": True, "input": None})
    first = field.WORKFLOW.settings({"umf": False, "input": str(tdr)})
    tdr.write_bytes(b"another one!")  # the same name and size
    second = field.WORKFLOW.settings({"umf": False, "input": str(tdr)})

    assert len({json.dumps(settings) for settings in (plain, umf, first, second)}) == 4


def test_jobs_drifted_in_another_solve_of_the_field_are_not_among_the_jobs_of_the_point(
    experiment: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(workflow.WORKFLOWS, "signal", experiment["workflow"])
    execute(experiment["workflow"], _kwargs())
    experiment["state"]["stamp"] = "second solve"
    execute(experiment["workflow"], _kwargs(seed=2))
    assert [len(jobs) for _, _, jobs, _ in workflow.jobs_of_points(experiment["root"])] == [1]

    execute(experiment["workflow"], _kwargs(seed=3))
    ((_, _, jobs, others),) = workflow.jobs_of_points(experiment["root"])
    assert workflow.batches(jobs) == "seed 2: 1 job, seed 3: 1 job"
    assert workflow.set_apart(others) == ["1 job measured something else and is not counted: other files or another field"]

