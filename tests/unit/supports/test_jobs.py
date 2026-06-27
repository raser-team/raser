import subprocess

import pytest

from raser.supports import jobs


def test_local_job_raises_when_worker_fails(monkeypatch):
    def fail(*args, **kwargs):
        raise subprocess.CalledProcessError(1, args[0])

    monkeypatch.setattr(jobs.subprocess, "run", fail)

    with pytest.raises(subprocess.CalledProcessError):
        jobs._run_local_job((0, ("timeres",), ["HPK-Si-PiN"]))


def test_local_job_uses_current_python_module(monkeypatch):
    calls = []

    def record(args, **kwargs):
        calls.append((args, kwargs))

    monkeypatch.setattr(jobs.subprocess, "run", record)
    monkeypatch.setattr(jobs.sys, "executable", "/env/python")

    jobs._run_local_job((2, ("timeres",), ["HPK-Si-PiN"]))

    assert calls == [
        (
            [
                "/env/python",
                "-m",
                "raser.cli.raser",
                "timeres",
                "HPK-Si-PiN",
                "--job",
                "2",
            ],
            {"shell": False, "check": True},
        )
    ]
