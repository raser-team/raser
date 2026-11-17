from __future__ import annotations

import json
from pathlib import Path

import pytest

from raser.cli.raser import main
from raser.lifecycle import jobs


@pytest.fixture
def work_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fields_ready: None) -> Path:
    root = tmp_path / "work"
    monkeypatch.setenv("RASER_WORK_PATH", str(root))
    monkeypatch.delenv("RASER_PROJECT_PATH", raising=False)
    monkeypatch.delenv("RASER_COMPONENT_PATH", raising=False)
    monkeypatch.chdir(tmp_path)
    return root


def _slices(out: str) -> list[str]:
    return [line.split()[0] for line in out.splitlines() if line.startswith("  ")]


def test_a_stage_command_on_a_device_runs_its_signal_up_to_that_stage(
    work_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["current", "HPK-Si-PiN", "--seed", "1", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert out.splitlines()[0].startswith(f"{work_root / 'HPK-Si-PiN' / 'signal' / 'seed_1'}: ")
    assert _slices(out) == ["deposit", "field", "current"]

    assert main(["dep", "HPK-Si-PiN", "--seed", "1", "--dry-run"]) == 0  # the short command
    assert _slices(capsys.readouterr().out) == ["deposit"]


def test_a_stage_command_on_an_experiment_folder_runs_that_experiment_and_records_full_names(
    work_root: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    submitted: list[tuple[str, ...]] = []
    monkeypatch.setattr(jobs, "run_indexed_jobs", lambda prefix, tail, *a, **k: submitted.append((*prefix, *tail[:3])))
    experiment = work_root / "HPK-Si-PiN" / "cce"

    assert main(["rdo", "HPK-Si-PiN", "--seed", "1", "-s", "2"]) == 0  # makes work/HPK-Si-PiN/signal
    assert main(["cce", "HPK-Si-PiN", "--seed", "1", "-s", "2"]) == 0
    submitted.clear()
    capsys.readouterr()
    assert main(["cur", str(experiment), "--seed", "2", "-s", "2"]) == 0

    assert _slices(capsys.readouterr().out) == ["deposit", "field", "current"]
    assert submitted == [("cce", "HPK-Si-PiN", "--job-slices", "deposit,field,current")]
    signal = json.loads((work_root / "HPK-Si-PiN" / "signal" / "config.json").read_text())
    assert signal["workflow"] == "signal"


def test_a_target_that_is_neither_an_experiment_nor_a_device_says_both_ways(work_root: Path) -> None:
    with pytest.raises(SystemExit, match="neither an experiment folder .* nor a device"):
        main(["readout", "no-such-thing", "--dry-run"])


def test_a_short_command_hands_its_jobs_the_full_name(
    work_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    submitted: list[tuple[str, ...]] = []
    monkeypatch.setattr(jobs, "run_indexed_jobs", lambda prefix, tail, *a, **k: submitted.append(tuple(prefix)))

    assert main(["-b", "fld", "HPK-Si-PiN"]) == 0

    assert submitted == [("field",)]


def test_raser_field_on_an_experiment_solves_the_fields_its_points_need_and_runs_none_of_its_jobs(
    work_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from raser.stages import field

    started: list[float] = []
    monkeypatch.setattr(field.SHARED, "ready", lambda options, files: None)
    monkeypatch.setattr(field.SHARED, "start", lambda kwargs, options, files: started.append(options["voltage"]))
    monkeypatch.setattr(jobs, "run_indexed_jobs", lambda *a, **k: pytest.fail("submitted"))
    experiment = work_root / "HPK-Si-PiN" / "signal"
    experiment.mkdir(parents=True)
    config = {"workflow": "signal", "device": "HPK-Si-PiN", "set": {}, "scan": {"voltage": [100, 300]}}
    (experiment / "config.json").write_text(json.dumps(config))

    assert main(["-b", "fld", str(experiment)]) == 0

    assert sorted(started) == [100, 300]
    assert sorted(path.name for path in experiment.iterdir()) == ["config.json"]


def test_raser_field_on_the_field_itself_names_its_device(work_root: Path) -> None:
    folder = work_root / "HPK-Si-PiN" / "field"
    folder.mkdir(parents=True)
    (folder / "config.json").write_text(json.dumps({"workflow": "field", "device": "HPK-Si-PiN"}))

    with pytest.raises(SystemExit, match="raser field HPK-Si-PiN"):
        main(["field", str(folder)])
