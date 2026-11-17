from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from raser.cli.raser import main
from raser.stages import field
from raser.lifecycle import jobs
from raser.supports import process


SOURCE_ROOT = Path(__file__).resolve().parents[2] / "src"


@pytest.fixture
def work_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fields_ready: None) -> Path:
    root = tmp_path / "work"
    monkeypatch.setenv("RASER_WORK_PATH", str(root))
    monkeypatch.delenv("RASER_PROJECT_PATH", raising=False)
    monkeypatch.delenv("RASER_COMPONENT_PATH", raising=False)
    return root


def test_help_does_not_load_scientific_runtimes() -> None:
    script = (
        "import sys\n"
        "from raser.cli.raser import APPLICATIONS, main\n"
        "for argv in [['--help'], *[[app, '--help'] for app in APPLICATIONS]]:\n"
        "    try:\n"
        "        main(argv)\n"
        "    except SystemExit as stop:\n"
        "        assert stop.code == 0, argv\n"
        "loaded = [m for m in ('ROOT', 'g4ppyy', 'devsim') if m in sys.modules]\n"
        "assert not loaded, loaded\n"
    )
    completed = subprocess.run(
        [sys.executable, "-c", script],
        env={**os.environ, "PYTHONPATH": str(SOURCE_ROOT)},
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr


def test_application_runs_inside_the_project_named_by_its_device(
    work_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[str | None] = []
    monkeypatch.setattr(
        field, "run", lambda kwargs: seen.append(os.environ.get("RASER_PROJECT_PATH"))
    )

    main(["field", "HPK-Si-PiN", "-iv"])

    assert seen == [str(work_root / "HPK-Si-PiN")]
    assert "RASER_PROJECT_PATH" not in os.environ


def test_failing_application_is_cleaned_up_before_its_error_propagates(
    work_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    released: list[str] = []

    def run(kwargs):
        process.at_process_end(lambda: released.append("runtime"))
        raise RuntimeError("field failed")

    monkeypatch.setattr(field, "run", run)

    with pytest.raises(RuntimeError, match="field failed"):
        main(["field", "HPK-Si-PiN"])
    assert released == ["runtime"]
    assert "RASER_PROJECT_PATH" not in os.environ


def test_what_an_application_returns_does_not_become_the_exit_status(
    work_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(field, "run", lambda kwargs: {"plan": "field"})

    assert main(["field", "HPK-Si-PiN"]) == 0


def test_global_batch_before_a_command_with_jobs_submits_each_job_itself(
    work_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    submitted: list[tuple[bool, int]] = []
    monkeypatch.setattr(
        jobs,
        "run_indexed_jobs",
        lambda *args, use_cluster, mem, **kwargs: submitted.append((use_cluster, mem)),
    )

    assert main(["-bb", "cce", "HPK-Si-PiN", "-s", "2", "--seed", "1"]) == 0
    assert main(["-b", "cce", "HPK-Si-PiN", "-s", "2", "--seed", "2", "-mem", "3"]) == 0

    assert submitted == [(True, 2), (True, 3)]


def test_global_test_before_a_command_with_jobs_is_its_dry_run(
    work_root: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    monkeypatch.setattr(
        jobs, "run_indexed_jobs", lambda *args, **kwargs: pytest.fail("submitted")
    )

    assert main(["-t", "-b", "cce", "HPK-Si-PiN", "-s", "2", "--seed", "1"]) == 0

    folder = work_root / "HPK-Si-PiN" / "cce" / "seed_1"
    slices = [f"  {name:<12}jobs [0, 1]" for name in ("deposit", "field", "current", "readout")]
    assert capsys.readouterr().out.splitlines() == [f"{folder}: jobs [0, 1]", *slices]
    assert not work_root.exists()


def test_inside_an_experiment_folder_the_command_and_device_come_from_its_config(
    work_root: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    submitted: list[tuple[list[str], bool, int]] = []
    monkeypatch.setattr(
        jobs,
        "run_indexed_jobs",
        lambda prefix, tail, count, *, use_cluster, mem, **kwargs: submitted.append(
            ([*prefix, *tail[:-2]], use_cluster, mem)
        ),
    )
    first = ["cce", "HPK-Si-PiN", "--scan", "voltage=200,300", "-s", "1", "--seed", "1"]
    assert main(first) == 0
    experiment = work_root / "HPK-Si-PiN" / "cce"
    monkeypatch.chdir(experiment)
    capsys.readouterr()

    assert main(["-s", "2", "--seed", "2", "--dry-run"]) == 0
    slices = [f"  {name:<12}jobs [0, 1]" for name in ("deposit", "field", "current", "readout")]
    assert capsys.readouterr().out.splitlines() == [
        f"{experiment / 'seed_2'}: jobs [0, 1]",
        *slices,
        f"{experiment / 'voltage_300' / 'seed_2'}: jobs [0, 1]",
        *slices,
    ]
    submitted.clear()
    assert main(["-bb", "-s", "2", "--seed", "3"]) == 0
    every = ["--job-slices", "deposit,field,current,readout"]  # each voltage is measured anew
    assert submitted == [(["cce", "HPK-Si-PiN", *every], True, 2)] * 2
