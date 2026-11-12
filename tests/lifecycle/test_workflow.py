from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from raser.lifecycle import jobs
from raser.lifecycle.workflow import Workflow
from raser.lifecycle.workflow import execute


@pytest.fixture
def started(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    """The job commands handed to the local pool or the cluster."""
    monkeypatch.setenv("RASER_WORK_PATH", str(tmp_path))
    monkeypatch.delenv("RASER_PROJECT_PATH", raising=False)
    monkeypatch.chdir(tmp_path)
    calls: list[Any] = []

    def run_indexed_jobs(prefix, tail, count, **options):
        calls.append((prefix, tail, count, options["use_cluster"]))

    monkeypatch.setattr(jobs, "run_indexed_jobs", run_indexed_jobs)
    return calls


def _kwargs(**given: Any) -> dict[str, Any]:
    kwargs = {"jobs": None, "batch": False, "mem": 1, "_entry_command_prefix": ("toy",)}
    return {**kwargs, **given}


def test_s_starts_that_many_jobs_of_the_same_command_in_the_work_folder(
    started: list[Any], tmp_path: Path
) -> None:
    workflow = Workflow(
        name="toy run", job=lambda options: None, command=lambda kwargs: ["--fast"]
    )

    execute(workflow, _kwargs(det_name="dev", jobs=3))

    folder = tmp_path / "toy" / "run"
    tail = ["run", "dev", "--fast", "--job-dir", str(folder)]
    assert started == [(("toy",), tail, 3, False)]


def test_without_s_the_single_job_runs_in_this_process_without_a_job_index(
    started: list[Any], tmp_path: Path
) -> None:
    received: list[dict[str, Any]] = []
    workflow = Workflow(name="toy", job=received.append, device=False)

    execute(workflow, _kwargs())

    assert started == []
    assert received[0].get("job_index") is None
    assert received[0]["_run_batch_path"] == str(tmp_path / "toy" / "batch")
    assert (tmp_path / "toy" / "batch").is_dir()


def test_b_without_s_submits_the_single_job_to_the_cluster(started: list[Any]) -> None:
    workflow = Workflow(name="toy", job=lambda options: None, device=False)

    execute(workflow, _kwargs(batch=True))

    assert [(count, cluster) for _, _, count, cluster in started] == [(1, True)]
