from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from raser.lifecycle import jobs
from raser.lifecycle.workflow import Workflow
from raser.lifecycle.workflow import execute


@pytest.fixture
def started(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    """The job commands handed to the local pool or the cluster; they finish."""
    monkeypatch.setenv("RASER_WORK_PATH", str(tmp_path))
    monkeypatch.delenv("RASER_PROJECT_PATH", raising=False)
    monkeypatch.chdir(tmp_path)
    calls: list[Any] = []

    def run_indexed_jobs(prefix, tail, count, *, indices, **options):
        calls.append((prefix, tail, list(indices), options["use_cluster"]))
        for index in indices:
            (Path(tail[-1]) / "batch" / f"job_{index}.done").touch()

    monkeypatch.setattr(jobs, "run_indexed_jobs", run_indexed_jobs)
    return calls


@pytest.fixture
def seeded(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """The seeds given to the generators, without loading ROOT."""
    seeds: list[int] = []
    seeding = SimpleNamespace(seed_generators=seeds.append)
    monkeypatch.setitem(sys.modules, "raser.core.seeding", seeding)
    return seeds


def _kwargs(**given: Any) -> dict[str, Any]:
    kwargs = {"jobs": None, "batch": False, "mem": 1, "seed": 42, "dry_run": False}
    return {**kwargs, "_entry_command_prefix": ("toy",), **given}


TOY = Workflow(name="toy", job=lambda options: None, device=False)


def test_s_starts_that_many_jobs_of_the_same_command_in_the_seed_folder(
    started: list[Any], tmp_path: Path
) -> None:
    workflow = Workflow(
        name="toy run", job=lambda options: None, command=lambda kwargs: ["--fast"]
    )

    execute(workflow, _kwargs(det_name="dev", jobs=3))

    folder = tmp_path / "toy" / "run" / "seed_42"
    tail = ["run", "dev", "--fast", "--job-dir", str(folder)]
    assert started == [(("toy",), tail, [0, 1, 2], False)]
    assert json.loads((folder / "run.json").read_text()) == {"seed": 42}


def test_without_s_the_single_job_runs_in_this_process_without_a_job_index(
    started: list[Any], seeded: list[int], tmp_path: Path
) -> None:
    received: list[dict[str, Any]] = []
    workflow = Workflow(name="toy", job=received.append, device=False)

    execute(workflow, _kwargs())
    execute(workflow, _kwargs())  # finished: nothing is left to run

    assert started == []
    assert len(received) == 1
    assert received[0].get("job_index") is None
    assert received[0]["_run_batch_path"] == str(tmp_path / "toy" / "seed_42" / "batch")
    assert seeded == [received[0]["seed"]]


def test_b_without_s_submits_the_single_job_to_the_cluster(started: list[Any]) -> None:
    execute(TOY, _kwargs(batch=True))

    assert [(indices, cluster) for _, _, indices, cluster in started] == [([0], True)]


def test_the_same_fixed_seed_again_starts_only_the_jobs_that_did_not_finish(
    started: list[Any],
) -> None:
    execute(TOY, _kwargs(jobs=2))
    execute(TOY, _kwargs(jobs=2))
    execute(TOY, _kwargs(jobs=4))

    assert [indices for _, _, indices, _ in started] == [[0, 1], [2, 3]]


def test_without_a_seed_the_folder_is_a_timestamp_and_the_drawn_seed_is_recorded(
    started: list[Any], tmp_path: Path
) -> None:
    execute(TOY, _kwargs(seed=None, jobs=2))

    (folder,) = (tmp_path / "toy").iterdir()
    assert not folder.name.startswith("seed_")
    assert isinstance(json.loads((folder / "run.json").read_text())["seed"], int)


def test_job_seeds_differ_within_a_run_repeat_exactly_and_do_not_overlap_between_runs(
    started: list[Any], seeded: list[int], tmp_path: Path
) -> None:
    def seeds_of(run_seed: int) -> list[int]:
        execute(TOY, _kwargs(seed=run_seed, jobs=2))
        folder = str(tmp_path / "toy" / f"seed_{run_seed}")
        seeded.clear()
        for index in (0, 1):
            execute(TOY, _kwargs(job_dir=folder, job_index=index))
        return list(seeded)

    first, again, neighbour = seeds_of(42), seeds_of(42), seeds_of(43)

    assert first[0] != first[1]
    assert again == first
    assert not set(first) & set(neighbour)
    assert all(0 < seed < 2**31 for seed in first)


def test_dry_run_prints_the_seed_folder_and_its_jobs_and_writes_nothing(
    started: list[Any], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    execute(TOY, _kwargs(jobs=2, dry_run=True))

    assert capsys.readouterr().out == f"{tmp_path / 'toy' / 'seed_42'}: jobs [0, 1]\n"
    assert started == []
    assert not (tmp_path / "toy").exists()
