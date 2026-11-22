"""Plan and execute indexed local or cluster jobs."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
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
    indices: Sequence[int] | None = None,
) -> IndexedJobPlan:
    if count <= 0:
        raise ValueError("Indexed job count must be positive")
    if mem <= 0:
        raise ValueError("Indexed job memory level must be positive")
    commands = tuple(
        tuple([*command_prefix, *tail, "--job-index", str(index)])
        for index in (range(count) if indices is None else indices)
    )
    return IndexedJobPlan(
        commands=commands,
        backend="cluster" if use_cluster else "local",
        destination=destination,
        memory_level=mem,
    )


def _run_local_job(command: tuple[str, ...], log: Path | None = None) -> None:
    """Run a job command here; with `log`, what it prints goes to the
    terminal and into that file both."""
    words = [sys.executable, "-m", "raser.cli.raser", *command]
    if log is None:
        subprocess.run(words, shell=False, check=True)
        return
    with open(log, "w") as file, subprocess.Popen(
        words, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
    ) as process:
        assert process.stdout is not None
        for line in process.stdout:
            sys.stdout.write(line)
            file.write(line)
    if process.returncode:
        raise subprocess.CalledProcessError(process.returncode, words)


# The last line of a Python traceback: the exception and its message.
_RAISED = re.compile(r"^[A-Za-z_][\w.]*(Error|Exception|Exit|Interrupt)\b")


def last_line(log: Path) -> str:
    """Why a job failed, from its log: the last exception it raised, else
    its last line. What Geant4 and ROOT print from C++ comes out of their
    buffers when the process ends, after the traceback."""
    lines = [line for line in (log.read_text().splitlines() if log.is_file() else ["no log"]) if line.strip()]
    return next((line for line in reversed(lines) if _RAISED.match(line)), lines[-1] if lines else "an empty log")


def run_indexed_jobs(
    command_prefix,
    tail,
    count,
    *,
    use_cluster,
    mem,
    destination,
    dry_run=False,
    indices=None,
    log_folder=None,
    submitted=None,
):
    plan = plan_indexed_jobs(
        command_prefix,
        tail,
        count,
        use_cluster=use_cluster,
        mem=mem,
        destination=destination,
        indices=indices,
    )
    if dry_run:
        return plan
    numbers = range(count) if indices is None else indices

    if use_cluster:
        from raser.lifecycle import scheduler

        accepted: list[int] = []
        failed: dict[int, Exception] = {}
        for index, command in zip(numbers, plan.commands):
            try:
                plan = scheduler.main(destination, command, mem, is_test=False)
            except Exception as exc:
                failed[index] = exc
            else:
                accepted.append(index)
                if submitted is not None:  # (job index, what the scheduler named it)
                    submitted(index, getattr(plan, "job_id", None))
        if failed:
            submission_state = (
                "queued" if os.environ.get("RASER_SUBMIT_QUEUE") else "accepted"
            )
            raise RuntimeError(
                f"Cluster {submission_state} indices {accepted}; "
                f"failed indices {list(failed)}"
            ) from next(iter(failed.values()))
        return plan

    # With log_folder, the log of job i is <log_folder>/job_<i>.log.
    logs = [None if log_folder is None else Path(log_folder) / f"job_{index}.log" for index in numbers]
    max_processes = min(len(plan.commands), os.cpu_count() or 4)
    with ProcessPoolExecutor(max_workers=max_processes) as executor:
        futures = [executor.submit(_run_local_job, command, *([log] if log else [])) for command, log in zip(plan.commands, logs)]
    errors = {
        index: (error, log)
        for index, future, log in zip(numbers, futures, logs)
        if (error := future.exception()) is not None
    }
    if errors:
        why = [f"\n  job {index}: {last_line(log)} ({log})" for index, (_, log) in errors.items() if log]
        raise RuntimeError(
            f"Local jobs failed for indices {list(errors)}" + "".join(why)
        ) from next(iter(errors.values()))[0]
    return plan
