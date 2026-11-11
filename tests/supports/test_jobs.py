from __future__ import annotations

import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import pytest

from raser.supports import jobs
from raser.supports import scheduler


def test_task_command_drops_the_listed_options_together_with_their_values() -> None:
    argv = [
        "signal",
        "Device A",
        "-s",
        "2",
        "--jobs=3",
        "--seed=4",
        "-b",
        "--dry-run",
        "-vol",
        "200",
    ]

    tail = jobs.command_tail(argv, ["signal"], {"-s", "--jobs"})

    assert tail == ["Device A", "--seed=4", "-vol", "200"]


def test_each_task_runs_the_shared_command_with_its_own_index() -> None:
    plan = jobs.plan_indexed_jobs(
        ["signal"],
        ["Device A", "--seed=4"],
        3,
        use_cluster=False,
        mem=1,
        destination="signal",
    )

    assert plan.commands == (
        ("signal", "Device A", "--seed=4", "--job-index", "0"),
        ("signal", "Device A", "--seed=4", "--job-index", "1"),
        ("signal", "Device A", "--seed=4", "--job-index", "2"),
    )


def test_cluster_run_submits_every_task_once_with_the_requested_memory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    submitted: list[tuple] = []
    monkeypatch.setattr(
        scheduler,
        "main",
        lambda destination, command, level, is_test=False: submitted.append(
            (destination, command[-1], level, is_test)
        ),
    )

    jobs.run_indexed_jobs(
        ["signal"], ["HPK-Si-PiN"], 3, use_cluster=True, mem=2, destination="signal"
    )

    assert submitted == [
        ("signal", "0", 2, False),
        ("signal", "1", 2, False),
        ("signal", "2", 2, False),
    ]


def test_failed_cluster_submission_does_not_stop_the_remaining_tasks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def submit(destination, command, level, is_test=False):
        calls.append(command[-1])
        if command[-1] == "1":
            raise RuntimeError("scheduler rejected job")

    monkeypatch.setattr(scheduler, "main", submit)

    with pytest.raises(
        RuntimeError, match=r"accepted indices \[0, 2\]; failed indices \[1\]"
    ):
        jobs.run_indexed_jobs(
            ["signal"], ["HPK-Si-PiN"], 3, use_cluster=True, mem=1, destination="signal"
        )
    assert calls == ["0", "1", "2"]


def test_failed_local_task_does_not_stop_the_remaining_tasks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started: list[tuple[str, ...]] = []

    def run(command, **kwargs):
        started.append(tuple(command))
        if command[-1] == "1":
            raise subprocess.CalledProcessError(2, command)

    # Threads share the replaced subprocess.run; spawned processes would not.
    monkeypatch.setattr(jobs, "ProcessPoolExecutor", ThreadPoolExecutor)
    monkeypatch.setattr(jobs.subprocess, "run", run)

    with pytest.raises(RuntimeError, match=r"failed for indices \[1\]$"):
        jobs.run_indexed_jobs(
            ["signal"],
            ["HPK-Si-PiN"],
            3,
            use_cluster=False,
            mem=1,
            destination="signal",
        )

    worker = (sys.executable, "-m", "raser.cli.raser", "signal", "HPK-Si-PiN")
    assert sorted(started) == [(*worker, "--job-index", str(i)) for i in range(3)]
