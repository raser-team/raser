"""IHEP cluster job planning and submission."""

from __future__ import annotations

import grp
import os
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from raser.supports.paths import project_path


@dataclass(frozen=True)
class ClusterJobPlan:
    job_file: Path
    worker_command: tuple[str, ...]
    submit_command: tuple[str, ...]

    def as_dict(self) -> dict:
        return {
            "job_file": str(self.job_file),
            "worker_command": list(self.worker_command),
            "submit_command": list(self.submit_command),
        }


def job_dir(destination_subfolder):
    return project_path(destination_subfolder, "jobs")


def _tokens(command: str | Sequence[str]) -> tuple[str, ...]:
    return tuple(
        shlex.split(command) if isinstance(command, str) else map(str, command)
    )


def plan_job(destination_subfolder, command, batch_level, *, group=None, image=None):
    if batch_level <= 0:
        raise ValueError("Batch memory level must be positive")
    command_tokens = _tokens(command)
    if not command_tokens:
        raise ValueError("Batch worker command must contain tokens")
    group_name = group or grp.getgrgid(os.stat(".").st_gid)[0]
    memory_mb = 8000 * batch_level
    directory = job_dir(destination_subfolder)
    command_name = "_".join(command_tokens).replace("/", "_")
    job_file = directory / f"{command_name}.job"
    if image:
        worker = (
            "/usr/bin/apptainer",
            "exec",
            "--env-file",
            ".raser/env",
            str(image),
            "raser",
            *command_tokens,
        )
    else:
        worker = ("raser", *command_tokens)
    submit = (
        "hep_sub",
        "-o",
        str(directory),
        "-e",
        str(directory),
        str(job_file),
        "-mem",
        str(memory_mb),
        "-g",
        group_name,
    )
    return ClusterJobPlan(job_file, worker, submit)


def main(destination_subfolder, command, batch_level, is_test=False):
    image = os.environ.get("IMGFILE")
    if image is None and not is_test:
        raise RuntimeError("IMGFILE must be set before cluster submission")
    plan = plan_job(
        destination_subfolder,
        command,
        batch_level,
        image=image,
    )
    if is_test:
        print(shlex.join(plan.submit_command))
        return plan
    gen_job(plan.job_file, shlex.join(plan.worker_command))
    submit_job(plan)
    return plan


def gen_job(jobfile_name, run_code):
    path = Path(jobfile_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(run_code) + "\n", encoding="utf-8")
    path.chmod(0o755)
    return path


def submit_job(plan: ClusterJobPlan):
    subprocess.run(plan.submit_command, shell=False, check=True)


def run_cmd(command, is_test=False):
    command_tokens = _tokens(command)
    if is_test:
        print(shlex.join(command_tokens))
        return command_tokens
    subprocess.run(command_tokens, shell=False, check=True)
    return command_tokens
