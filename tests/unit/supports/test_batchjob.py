import subprocess

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
