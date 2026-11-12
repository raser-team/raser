"""`raser <command> -s <n>`: run n independent jobs in a seed folder."""

from __future__ import annotations

import argparse
import hashlib
import json
import secrets
import time
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
        parser.add_argument("--seed", type=int)
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--job-dir", help=argparse.SUPPRESS)
        parser.add_argument("--job-index", type=int, help=argparse.SUPPRESS)
        parser.set_defaults(_run=lambda kwargs: execute(self, kwargs))


def execute(workflow, kwargs):
    if kwargs.get("job_dir"):
        return _run_job(workflow, kwargs)  # one of the jobs started below

    # The seed folder of this command, and the jobs that are left in it.
    if kwargs["seed"] is None:
        label, seed = time.strftime("%Y_%m%d_%H%M%S"), secrets.randbits(31)
    else:
        label, seed = f"seed_{kwargs['seed']}", kwargs["seed"]
    folder = Path(project_path(*workflow.words)) / label
    left = [i for i in range(kwargs["jobs"] or 1) if not _done(folder, i).exists()]
    print(f"{folder}: jobs {left}")
    if kwargs["dry_run"] or not left:
        return None

    (folder / "batch").mkdir(parents=True, exist_ok=True)
    (folder / "run.json").write_text(json.dumps({"seed": seed}, indent=2) + "\n")
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
        len(left),
        use_cluster=kwargs["batch"],
        mem=kwargs["mem"],
        destination=workflow.words[0],
        indices=left,
    )
    return None


def _run_job(workflow, kwargs):
    """One job: its seed is a hash of the seed in run.json and its number."""
    from raser.core.seeding import seed_generators  # loads ROOT

    folder, index = Path(kwargs["job_dir"]), kwargs.get("job_index") or 0
    record = json.loads((folder / "run.json").read_text())
    digest = hashlib.sha256(f"{record['seed']}/{index}".encode()).digest()
    options = dict(kwargs)
    options["seed"] = 1 + int.from_bytes(digest[:8], "big") % (2**31 - 1)
    options["_run_path"] = str(folder)
    options["_run_batch_path"] = str(folder / "batch")
    seed_generators(options["seed"])
    workflow.job(options)
    _done(folder, index).touch()


def _done(folder, index) -> Path:
    return folder / "batch" / f"job_{index}.done"
