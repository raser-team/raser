from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from raser.cli import raser
from raser.cli.raser import main
from raser.core.field import command as field_command
from raser.supports import lifecycle


SOURCE_ROOT = Path(__file__).resolve().parents[2] / "src"


@pytest.fixture
def work_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
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
        field_command,
        "main",
        lambda kwargs: seen.append(os.environ.get("RASER_PROJECT_PATH")),
    )

    main(["field", "HPK-Si-PiN"])

    assert seen == [str(work_root / "HPK-Si-PiN")]
    assert "RASER_PROJECT_PATH" not in os.environ


def test_failing_application_is_cleaned_up_before_its_error_propagates(
    work_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    released: list[str] = []

    def run(kwargs):
        lifecycle.at_process_end(lambda: released.append("runtime"))
        raise RuntimeError("field failed")

    monkeypatch.setattr(field_command, "main", run)

    with pytest.raises(RuntimeError, match="field failed"):
        main(["field", "HPK-Si-PiN"])
    assert released == ["runtime"]
    assert "RASER_PROJECT_PATH" not in os.environ


def test_what_an_application_returns_does_not_become_the_exit_status(
    work_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(field_command, "main", lambda kwargs: {"plan": "field"})

    assert main(["field", "HPK-Si-PiN"]) == 0


def test_global_batch_submits_the_command_without_the_global_options(
    work_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    submitted: list[list[str]] = []
    monkeypatch.setattr(
        raser.batchjob,
        "main",
        lambda destination, command, level, is_test=False: submitted.append(
            list(command)
        ),
    )
    monkeypatch.setattr(
        field_command, "main", lambda kwargs: pytest.fail("ran in this process")
    )

    main(["-t", "-bb", "field", "HPK-Si-PiN", "-bias", "-200"])

    assert submitted == [["field", "HPK-Si-PiN", "-bias", "-200"]]
