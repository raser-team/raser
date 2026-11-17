from __future__ import annotations

import json
from pathlib import Path

from raser.lifecycle import status
from raser.lifecycle import workflow as workflow_module
from raser.lifecycle.slices import Shared
from raser.lifecycle.slices import Slice
from raser.lifecycle.slices import mark
from raser.lifecycle.workflow import Workflow

FIELD = Shared(ready=lambda options, files: None, start=lambda kwargs, options, files: None)
CHAIN = Workflow(
    name="toy",
    keys=("x",),
    slices=(Slice("deposit", print), Slice("field", print, shared=FIELD), Slice("current", print)),
    device=False,
)


def _folder(tmp_path: Path, jobs: int) -> tuple[Path, dict]:
    folder = tmp_path / "toy" / "seed_1"
    (folder / "batch").mkdir(parents=True)
    record = {"seed": 1, "point": "", "jobs": jobs, "held_in": dict.fromkeys(("deposit", "field", "current"), "")}
    (folder / "run.json").write_text(json.dumps(record))
    return folder, record


def test_the_jobs_of_a_slice_are_done_running_failed_waiting_or_not_started(tmp_path: Path) -> None:
    folder, record = _folder(tmp_path, 4)
    for name in ("deposit", "field", "current"):
        mark(folder, 0, name).touch()  # job 0: all done
    for i in (1, 2):
        mark(folder, i, "deposit").touch()
        mark(folder, i, "field").touch()
    held = workflow_module._lock(folder / "batch" / "job_1.lock", "job 1")  # job 1 runs
    (folder / "batch" / "job_2.log").write_text("RuntimeError: x\n")  # job 2 failed
    # job 3: nothing yet

    states = status.folder_states(CHAIN, folder, record, ready=lambda piece: True)
    held.close()

    assert states["deposit"]["done"] == [0, 1, 2] and states["deposit"]["not started"] == [3]
    assert states["current"]["done"] == [0]
    assert states["current"]["running"] == [1]
    assert states["current"]["failed"] == [2]
    assert states["current"]["waiting"] == [3]


def test_a_shared_slice_that_is_not_ready_makes_its_jobs_wait(tmp_path: Path) -> None:
    folder, record = _folder(tmp_path, 1)
    mark(folder, 0, "deposit").touch()

    states = status.folder_states(CHAIN, folder, record, ready=lambda piece: False)

    assert states["field"]["waiting"] == [0]


def test_a_seed_folder_run_with_other_options_is_out_of_date_not_done(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("RASER_PROJECT_PATH", str(tmp_path))
    plain = Workflow(name="toy", job=print, keys=("x",), defaults={"x": 1}, device=False)
    (tmp_path / "toy").mkdir()
    (tmp_path / "toy" / "config.json").write_text(json.dumps({"workflow": "toy", "set": {"x": 2}}))
    folder = tmp_path / "toy" / "seed_1"
    (folder / "batch").mkdir(parents=True)
    (folder / "run.json").write_text(json.dumps({"seed": 1, "point": "", "options": {"x": 1}, "files": {}, "jobs": 1}))
    mark(folder, 0).touch()

    lines = status._lines(plain, tmp_path / "toy", {"scan": []})

    assert lines[0].startswith(f"{folder}: out of date")
    assert lines[1].split() == ["job", "1/1", "done,", "out", "of", "date"]


def test_an_experiment_inside_is_no_seed_folder_and_a_point_without_runs_is_not_started(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("RASER_PROJECT_PATH", str(tmp_path))
    plain = Workflow(name="toy", job=print, keys=("x",), defaults={"x": 1}, device=False)
    root = tmp_path / "toy"
    (root / "analysis").mkdir(parents=True)
    (root / "config.json").write_text(json.dumps({"workflow": "toy", "scan": {"x": [1, 2]}}))
    (root / "analysis" / "run.json").write_text(json.dumps({"point": "", "options": {}}))  # no seed

    lines = status._lines(plain, root, {"scan": []})

    assert lines == [f"{root}: not started", f"{root / 'x_2'}: not started"]
