from __future__ import annotations

from pathlib import Path

import pytest

from raser.cli.raser import main


def test_dry_run_names_the_seed_folder_of_every_point_and_writes_nothing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    work_root = tmp_path / "work"
    monkeypatch.setenv("RASER_WORK_PATH", str(work_root))
    monkeypatch.delenv("RASER_PROJECT_PATH", raising=False)
    command = "cce HPK-Si-PiN -s 2 --scan voltage=200,300 --seed 42 --dry-run"

    assert main(command.split()) == 0
    lines = capsys.readouterr().out.splitlines()

    experiment = work_root / "HPK-Si-PiN" / "cce"
    slices = [f"  {name:<15}jobs [0, 1]" for name in ("deposit", "field", "current", "readout", "reconstruction")]
    assert lines == [
        f"{experiment / 'seed_42'}: jobs [0, 1]",
        *slices,
        f"{experiment / 'voltage_300' / 'seed_42'}: jobs [0, 1]",
        *slices,
    ]
    assert not work_root.exists()


def test_tct_dry_run_names_the_point_folders_under_the_tct_experiment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    work_root = tmp_path / "work"
    monkeypatch.setenv("RASER_WORK_PATH", str(work_root))
    monkeypatch.delenv("RASER_PROJECT_PATH", raising=False)
    command = "tct HPK-Si-PiN SPA_top_Si_IR --scan voltage=200,300"

    assert main([*command.split(), "--dry-run"]) == 0
    lines = capsys.readouterr().out.splitlines()

    experiment = work_root / "HPK-Si-PiN" / "tct"
    slices = [f"  {name:<12}jobs [0]" for name in ("current", "readout")]
    assert lines == [
        f"{experiment}: jobs [0]",
        *slices,
        f"{experiment / 'voltage_300'}: jobs [0]",
        *slices,
    ]
    assert not work_root.exists()
