"""Plan and execute indexed local or cluster jobs."""

from __future__ import annotations

import os
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class IndexedJobPlan:
    commands: tuple[tuple[str, ...], ...]
    backend: str
    destination: str
    memory_level: int

    def as_dict(self) -> dict:
        return {
            "backend": self.backend,
            "destination": self.destination,
            "memory_level": self.memory_level,
            "commands": [list(command) for command in self.commands],
        }


def command_tail(argv, command_prefix, remove_options):
    tail = list(argv)
    prefix = list(command_prefix)
    if tail[: len(prefix)] == prefix:
        tail = tail[len(prefix) :]

    cleaned = []
    skip_next = False
    for item in tail:
        if skip_next:
            skip_next = False
            continue
        if item in remove_options:
            skip_next = True
            continue
        if any(item.startswith(option + "=") for option in remove_options):
            continue
        if item in ("-b", "--batch", "--dry-run"):
            continue
        cleaned.append(item)
    return cleaned


def plan_indexed_jobs(
    command_prefix: Sequence[str],
    tail: Sequence[str],
    count: int,
    *,
    use_cluster: bool,
    mem: int,
    destination: str,
) -> IndexedJobPlan:
    if count <= 0:
        raise ValueError("Indexed job count must be positive")
    if mem <= 0:
        raise ValueError("Indexed job memory level must be positive")
    commands = tuple(
        tuple([*command_prefix, *tail, "--job", str(index)]) for index in range(count)
    )
    return IndexedJobPlan(
        commands=commands,
        backend="cluster" if use_cluster else "local",
        destination=destination,
        memory_level=mem,
    )


def _run_local_job(command: tuple[str, ...]) -> None:
    subprocess.run(
        [sys.executable, "-m", "raser.cli.raser", *command],
        shell=False,
        check=True,
    )


def run_indexed_jobs(
    command_prefix,
    tail,
    count,
    *,
    use_cluster,
    mem,
    destination,
    dry_run=False,
):
    plan = plan_indexed_jobs(
        command_prefix,
        tail,
        count,
        use_cluster=use_cluster,
        mem=mem,
        destination=destination,
    )
    if dry_run:
        return plan

    if use_cluster:
        from raser.supports import batchjob

        accepted: list[int] = []
        for index, command in enumerate(plan.commands):
            try:
                batchjob.main(destination, command, mem, is_test=False)
            except Exception as exc:
                pending = list(range(index, len(plan.commands)))
                raise RuntimeError(
                    f"Cluster accepted indices {accepted}; pending indices {pending}"
                ) from exc
            accepted.append(index)
        return plan

    max_processes = min(count, os.cpu_count() or 4)
    with ProcessPoolExecutor(max_workers=max_processes) as executor:
        list(executor.map(_run_local_job, plan.commands))
    return plan
