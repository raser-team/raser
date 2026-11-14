from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from raser.apps import cce
from raser.apps.signal.runtime import apply_signal_plan
from raser.cli.raser import main
from raser.lifecycle import workflow
from raser.supports.paths import project_root_context


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
    assert lines == [
        f"{experiment / 'seed_42'}: jobs [0, 1]",
        f"{experiment / 'voltage_300' / 'seed_42'}: jobs [0, 1]",
    ]
    assert not work_root.exists()


def test_tct_dry_run_names_the_seed_folders_under_the_tct_signal_experiment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    work_root = tmp_path / "work"
    monkeypatch.setenv("RASER_WORK_PATH", str(work_root))
    monkeypatch.delenv("RASER_PROJECT_PATH", raising=False)
    command = "tct signal HPK-Si-PiN SPA_top_Si_IR --scan voltage=200,300 --seed 42"

    assert main([*command.split(), "--dry-run"]) == 0
    lines = capsys.readouterr().out.splitlines()

    experiment = work_root / "HPK-Si-PiN" / "tct" / "signal"
    assert lines == [
        f"{experiment / 'seed_42'}: jobs [0]",
        f"{experiment / 'voltage_300' / 'seed_42'}: jobs [0]",
    ]
    assert not work_root.exists()


def test_signal_runtime_configures_the_detector_from_the_components_of_the_app(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "work" / "HPK-Si-PiN"
    monkeypatch.setenv("RASER_WORK_PATH", str(tmp_path / "work"))
    monkeypatch.setenv("RASER_PROJECT_PATH", str(project))
    kwargs: dict[str, Any] = {
        "det_name": "HPK-Si-PiN",
        "source": "decay/Sr90",
        "amplifier": None,
        "adc": None,
        "voltage": None,
        "irradiation": None,
        "events_per_job": 4,
        "jobs": None,
        "seed": 7,
        "run": "run-1",
    }
    with project_root_context(project, ("cce", "signal")):
        options, files = workflow._point(cce.WORKFLOW, kwargs, cce.WORKFLOW.defaults)
    kwargs.update(options, _files=files, _signal_label="cce")
    detector = SimpleNamespace(daq=None)

    g4_config = apply_signal_plan(detector, kwargs)

    assert detector.g4experiment == "charge_collection"
    assert g4_config["geant4_model"] == "charge_collection"
    assert g4_config["source_kind"] == "decay_source"
    assert detector.amplifier == "Broad_Band_UCSC"
    assert detector.daq == "scope"
    assert detector.signal_source == "Sr90"
    assert detector.signal_output_label == "cce"


def test_global_batch_test_keeps_commands_structured_and_scheduler_idle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    work_root = tmp_path / "work"
    monkeypatch.setenv("RASER_WORK_PATH", str(work_root))
    monkeypatch.delenv("RASER_PROJECT_PATH", raising=False)

    assert main(["-t", "-b", "tct", "position_scan_draw", "HPK-Si-PiN", "SPA_top_Si"]) == 0
    assert "hep_sub" in capsys.readouterr().out
    assert not work_root.exists()
