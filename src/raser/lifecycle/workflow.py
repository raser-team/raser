"""`raser <command> -s <n>`: run n independent jobs of one application."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from raser.lifecycle import jobs
from raser.supports.paths import project_path


@dataclass(frozen=True)
class Workflow:
    """What an application hands in."""

    name: str  # command words, "cce" or "tct signal"; folder work/<device>/<words>
    job: Callable  # runs one job; receives the options as a dict
    device: bool = True  # the command names a device
    command: Callable | None = None  # extra words of the job command

    @property
    def words(self):
        return self.name.split()

    def attach(self, parser):
        parser.add_argument("-s", "--jobs", type=int)
        parser.add_argument("-b", "--batch", action="store_true")
        parser.add_argument("-mem", type=int, default=1)
        parser.add_argument("--job-dir", help=argparse.SUPPRESS)
        parser.add_argument("--job-index", type=int, help=argparse.SUPPRESS)
        parser.set_defaults(_run=lambda kwargs: execute(self, kwargs))


def execute(workflow, kwargs):
    if kwargs.get("job_dir"):
        return _run_job(workflow, kwargs)  # one of the jobs started below

    folder = Path(project_path(*workflow.words))
    (folder / "batch").mkdir(parents=True, exist_ok=True)
    if kwargs["jobs"] is None and not kwargs["batch"]:
        return _run_job(workflow, {**kwargs, "job_dir": str(folder)})  # in this process
    tail = workflow.words[1:]
    if workflow.device:
        tail.append(kwargs["det_name"])
    if workflow.command:
        tail += workflow.command(kwargs)
    jobs.run_indexed_jobs(
        kwargs["_entry_command_prefix"],
        [*tail, "--job-dir", str(folder)],
        kwargs["jobs"] or 1,
        use_cluster=kwargs["batch"],
        mem=kwargs["mem"],
        destination=workflow.words[0],
    )
    return None


def _run_job(workflow, kwargs):
    """One job: it is told its folder and its number."""
    folder, index = Path(kwargs["job_dir"]), kwargs.get("job_index") or 0
    options = dict(kwargs)
    options["seed"] = index + 1  # ROOT reads seed 0 as "take one from the clock"
    options["_run_path"] = str(folder)
    options["_run_batch_path"] = str(folder / "batch")
    workflow.job(options)
