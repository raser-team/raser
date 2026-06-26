"""Helpers for indexed local and batch jobs."""

from __future__ import annotations

import os
import subprocess
from concurrent.futures import ProcessPoolExecutor


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
        if item in ("-b", "--batch"):
            continue
        cleaned.append(item)
    return cleaned


def _run_local_job(args):
    index, command_prefix, tail = args
    command_args = [*command_prefix, *tail, "--job", str(index)]
    print(" ".join(command_args))
    subprocess.run(["raser", *command_args], shell=False)


def run_indexed_jobs(command_prefix, tail, count, *, use_cluster, mem, destination):
    if use_cluster:
        from raser.supports import batchjob

        for index in range(count):
            command_args = [*command_prefix, *tail, "--job", str(index)]
            command = " ".join(command_args)
            print(command)
            batchjob.main(destination, command, mem, is_test=False)
        return

    max_processes = min(count, os.cpu_count() or 4)
    task_args = [(index, command_prefix, tail) for index in range(count)]
    with ProcessPoolExecutor(max_workers=max_processes) as executor:
        executor.map(_run_local_job, task_args)
