from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from raser.lifecycle import scheduler
from raser.lifecycle import workflow
from raser.lifecycle.slices import Slice
from raser.lifecycle.workflow import Workflow
from raser.lifecycle.workflow import execute

TOY = Workflow(
    name="toy",
    slices=(Slice("first", lambda options: None), Slice("second", lambda options: None)),
    device=False,
)


@pytest.fixture
def cluster(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Jobs submitted to a cluster that names them 100, 101, ...; nothing runs them."""
    monkeypatch.setenv("RASER_PROJECT_PATH", str(tmp_path))
    monkeypatch.delenv("RASER_CLUSTER_JOB", raising=False)
    monkeypatch.delenv("RASER_RESUBMIT_DEPTH", raising=False)
    monkeypatch.delenv("RASER_SUBMIT_QUEUE", raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(workflow, "_commit", lambda: "abc")
    monkeypatch.setitem(sys.modules, "raser.core.seeding", SimpleNamespace(seed_generators=lambda seed: None))
    submitted: list[str] = []

    def main(destination, command, mem, is_test=False):
        submitted.append(command[-1])
        return SimpleNamespace(job_id=str(100 + int(command[-1])))

    monkeypatch.setattr(scheduler, "main", main)
    return {"submitted": submitted, "folder": tmp_path / "toy" / "seed_1"}


def _kwargs(**given: Any) -> dict[str, Any]:
    kwargs: dict[str, Any] = {"jobs": 2, "batch": True, "mem": 1, "seed": 1, "dry_run": False, "scan": []}
    kwargs.update(same_seeds=False, _entry_command_prefix=("toy",), _argv=["-b", "toy", "-s", "2", "--seed", "1"])
    return {**kwargs, **given}


def test_a_job_submitted_is_recorded_for_each_of_its_slices_with_its_name_on_the_cluster(cluster: dict[str, Any]) -> None:
    execute(TOY, _kwargs())

    batch = cluster["folder"] / "batch"
    assert cluster["submitted"] == ["0", "1"]
    assert json.loads((batch / "second_1.submitted").read_text())["job"] == "101"
    assert sorted(path.name for path in batch.glob("*.submitted")) == [
        "first_0.submitted", "first_1.submitted", "second_0.submitted", "second_1.submitted"
    ]


@pytest.mark.parametrize(("alive", "again"), [(True, []), (False, ["0", "1"]), (None, [])])
def test_a_job_submitted_already_is_submitted_again_only_when_the_cluster_no_more_holds_it(
    cluster: dict[str, Any], monkeypatch: pytest.MonkeyPatch, alive: bool | None, again: list[str]
) -> None:
    execute(TOY, _kwargs())
    cluster["submitted"].clear()
    monkeypatch.setattr(scheduler, "job_alive", lambda job: alive)

    execute(TOY, _kwargs())

    assert cluster["submitted"] == again
    assert (cluster["folder"] / "batch" / "first_0.submitted").exists()  # recorded anew, or kept


def test_on_the_cluster_a_command_started_again_submits_only_what_was_never_submitted(
    cluster: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    execute(TOY, _kwargs())
    (cluster["folder"] / "batch" / "first_1.submitted").unlink()
    (cluster["folder"] / "batch" / "second_1.submitted").unlink()
    cluster["submitted"].clear()
    monkeypatch.setenv("RASER_CLUSTER_JOB", "1")
    monkeypatch.setattr(scheduler, "job_alive", lambda job: pytest.fail("asked the scheduler"))

    execute(TOY, _kwargs())

    assert cluster["submitted"] == ["1"]


def _job(cluster: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    """Run job 0 of the seed folder here as the cluster would; the commands it starts again."""
    started: list[list[str]] = []
    monkeypatch.setattr(
        workflow.subprocess, "run", lambda words, **kwargs: started.append([*words[3:], kwargs["env"]["RASER_RESUBMIT_DEPTH"]])
    )
    workflow._run_job(TOY, {"job_dir": str(cluster["folder"]), "job_index": 0, "job_slices": "first,second"})
    return started


def test_a_job_on_the_cluster_that_made_progress_starts_the_command_again_in_its_seed_folder(
    cluster: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    execute(TOY, _kwargs())
    monkeypatch.setenv("RASER_CLUSTER_JOB", "1")
    monkeypatch.setenv("RASER_RESUBMIT_DEPTH", "1")

    started = _job(cluster, monkeypatch)

    assert started == [["-b", "toy", "-s", "2", "--seed", "1", "--seed-folder", "seed_1", "2"]]
    assert not list((cluster["folder"] / "batch").glob("*_0.submitted"))  # done: the records go


def test_a_job_without_progress_or_too_deep_does_not_start_the_command_again(
    cluster: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    execute(TOY, _kwargs())
    monkeypatch.setenv("RASER_CLUSTER_JOB", "1")
    monkeypatch.setenv("RASER_RESUBMIT_DEPTH", "2")  # as many as the slices
    assert _job(cluster, monkeypatch) == []

    monkeypatch.setenv("RASER_RESUBMIT_DEPTH", "0")
    assert _job(cluster, monkeypatch) == []  # its marks are there already: no progress


def test_going_on_in_a_seed_folder_named_by_its_time_makes_no_new_one(
    cluster: dict[str, Any], tmp_path: Path
) -> None:
    execute(TOY, _kwargs(seed=None))
    (label,) = [path.name for path in (tmp_path / "toy").iterdir() if path.is_dir()]

    execute(TOY, _kwargs(seed=None, seed_folder=label))

    assert [path.name for path in (tmp_path / "toy").iterdir() if path.is_dir()] == [label]


def test_through_the_queue_of_the_host_nothing_is_recorded_and_the_command_says_so(
    cluster: dict[str, Any], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("RASER_SUBMIT_QUEUE", "queue.txt")
    monkeypatch.setattr(scheduler, "main", lambda *a, **k: SimpleNamespace(job_id=None))

    execute(TOY, _kwargs())

    assert "is not started again by itself" in capsys.readouterr().out
    assert not list((cluster["folder"] / "batch").glob("*.submitted"))
