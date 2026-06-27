import subprocess

import pytest

from raser.supports import batchjob


def test_gen_job_writes_run_code(tmp_path):
    job_file = tmp_path / "job.sh"

    batchjob.gen_job(job_file, "raser current model")

    assert job_file.read_text(encoding="utf-8") == "raser current model"


def test_run_cmd_prints_command_in_test_mode(capsys):
    batchjob.run_cmd("hep_sub job.sh", is_test=True)

    assert capsys.readouterr().out == "hep_sub job.sh\n"


def test_run_cmd_executes_shell_command_outside_test_mode(monkeypatch):
    calls = []
    monkeypatch.setattr(
        subprocess, "run", lambda *args, **kwargs: calls.append((args, kwargs))
    )

    batchjob.run_cmd("hep_sub job.sh")

    assert calls == [((["hep_sub job.sh"],), {"shell": True})]


def test_submit_job_builds_hep_sub_command(tmp_path, monkeypatch):
    monkeypatch.setenv("RASER_PROJECT_PATH", str(tmp_path))
    job_file = tmp_path / "current" / "jobs" / "run.job"
    job_file.parent.mkdir(parents=True)
    job_file.write_text("raser current model", encoding="utf-8")
    calls = []
    monkeypatch.setattr(
        batchjob,
        "run_cmd",
        lambda command, is_test=False: calls.append((command, is_test)),
    )

    batchjob.submit_job(
        str(job_file),
        destination_subfolder="current",
        group="atlas",
        mem=16000,
        is_test=True,
    )

    assert calls == [
        (
            f"hep_sub -o {tmp_path / 'current' / 'jobs'} -e {tmp_path / 'current' / 'jobs'} "
            f"{job_file} -mem 16000 -g atlas",
            True,
        )
    ]
    assert job_file.stat().st_mode & 0o777 == 0o755


def test_job_dir_uses_project_path(tmp_path, monkeypatch):
    monkeypatch.setenv("RASER_PROJECT_PATH", str(tmp_path / "HPK-Si-PiN"))

    assert batchjob.job_dir("field") == tmp_path / "HPK-Si-PiN" / "field" / "jobs"


def test_main_fails_visibly_without_imgfile_for_real_submit(tmp_path, monkeypatch):
    monkeypatch.setenv("RASER_PROJECT_PATH", str(tmp_path / "HPK-Si-PiN"))
    monkeypatch.delenv("IMGFILE", raising=False)

    with pytest.raises(RuntimeError, match="IMGFILE"):
        batchjob.main("field", "field solve HPK-Si-PiN", 1, is_test=False)


def test_main_can_dry_run_without_imgfile(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("RASER_PROJECT_PATH", str(tmp_path / "HPK-Si-PiN"))
    monkeypatch.delenv("IMGFILE", raising=False)
    monkeypatch.setattr(batchjob.grp, "getgrgid", lambda gid: ["atlas"])

    batchjob.main("field", "field solve HPK-Si-PiN", 1, is_test=True)

    job_file = tmp_path / "HPK-Si-PiN" / "field" / "jobs" / "field_solve_HPK-Si-PiN.job"
    assert job_file.read_text() == "raser field solve HPK-Si-PiN"
    assert f"hep_sub -o {job_file.parent} -e {job_file.parent} {job_file}" in capsys.readouterr().out
