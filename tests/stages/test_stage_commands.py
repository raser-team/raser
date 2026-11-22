from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from raser_app.cflm import PADS
from raser.cli.raser import main
from raser.lifecycle import jobs
from raser.supports.paths import app_component_root


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
    experiment = work_root / "HPK-Si-PiN" / "signal"

    assert main(["rdo", "HPK-Si-PiN", "--seed", "1", "-s", "2"]) == 0  # makes work/HPK-Si-PiN/signal
    assert main(["signal", "HPK-Si-PiN", "--seed", "1", "-s", "2"]) == 0
    submitted.clear()
    capsys.readouterr()
    assert main(["cur", str(experiment), "--seed", "2", "-s", "2"]) == 0

    assert _slices(capsys.readouterr().out) == ["deposit", "field", "current"]
    assert submitted == [("signal", "HPK-Si-PiN", "--job-slices", "deposit,field,current")]
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


def test_a_stage_command_on_an_experiment_with_a_slice_per_position_runs_all_of_them_up_to_that_stage(
    work_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    experiment = work_root / "HPK-Si-PiN" / "cflm"
    experiment.mkdir(parents=True)
    (experiment / "config.json").write_text(json.dumps({"workflow": "cflm", "device": "HPK-Si-PiN"}))

    assert main(["current", str(experiment), "--seed", "1", "--dry-run"]) == 0

    ran = _slices(capsys.readouterr().out)
    assert ran[:2] == ["deposit", "field"]
    assert ran[2:] == [f"current.{pad}" for pad in PADS]


def test_a_batch_stage_command_given_a_relative_folder_records_where_it_is(
    work_root: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(jobs, "run_indexed_jobs", lambda *a, **k: None)
    assert main(["rdo", "HPK-Si-PiN", "--seed", "1", "--dry-run"]) == 0
    experiment = work_root / "HPK-Si-PiN" / "signal"
    experiment.mkdir(parents=True, exist_ok=True)
    (experiment / "config.json").write_text(json.dumps({"workflow": "signal", "device": "HPK-Si-PiN"}))

    assert main(["-b", "cur", "work/HPK-Si-PiN/signal", "--seed", "1"]) == 0

    record = json.loads((experiment / "seed_1" / "run.json").read_text())
    target = record["command"][record["command"].index("cur") + 1]
    assert Path(record["cwd"], target).resolve() == experiment.resolve()


@pytest.mark.parametrize("option", ["--scan", "--set"])
def test_raser_field_on_an_experiment_solves_the_field_of_a_point_given_on_its_command_line(
    work_root: Path, monkeypatch: pytest.MonkeyPatch, option: str
) -> None:
    from raser.stages import field

    started: list[float] = []
    monkeypatch.setattr(field.SHARED, "ready", lambda options, files: None)
    monkeypatch.setattr(field.SHARED, "start", lambda kwargs, options, files: started.append(options["voltage"]))
    experiment = work_root / "HPK-Si-PiN" / "signal"
    experiment.mkdir(parents=True)
    config = {"workflow": "signal", "device": "HPK-Si-PiN", "set": {}, "scan": {"voltage": [100, 300]}}
    (experiment / "config.json").write_text(json.dumps(config))

    assert main(["-b", "fld", str(experiment), option, "voltage=200"]) == 0

    assert started == [200]
    assert json.loads((experiment / "config.json").read_text()) == config


def test_reco_runs_the_chain_up_to_the_reconstruction_of_the_waveforms(
    work_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["reco", "HPK-Si-PiN", "--seed", "1", "--edge", "rising", "--dry-run"]) == 0

    assert _slices(capsys.readouterr().out) == ["deposit", "field", "current", "readout", "reconstruction"]


def test_ana_is_the_last_stage_of_the_chain_and_the_whole_chain_ends_in_it(
    work_root: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from raser.stages import analysis

    analysed: list[tuple[Path, str]] = []
    monkeypatch.setattr(analysis, "collect", lambda root: analysed.append((root, os.environ["RASER_COMPONENT_PATH"])))
    monkeypatch.setattr(jobs, "run_indexed_jobs", lambda *a, **k: None)
    experiment = work_root / "HPK-Si-PiN" / "signal"

    assert main(["ana", "HPK-Si-PiN", "--seed", "1", "-s", "2"]) == 0  # every slice before it, then the analysis
    assert _slices(capsys.readouterr().out) == ["deposit", "field", "current", "readout", "reconstruction"]
    assert main(["signal", "HPK-Si-PiN", "--seed", "1", "-s", "2"]) == 0  # the command of the experiment too
    assert main(["rdo", str(experiment), "--seed", "1", "-s", "2"]) == 0  # a stage before it stops there

    assert [root for root, _ in analysed] == [experiment, experiment]
    # the components are found as the command of the experiment finds them
    assert analysed[0][1].split(os.pathsep)[0] == str(app_component_root("raser_bench/signal"))


def test_ana_on_an_experiment_whose_chain_has_no_analysis_says_so(work_root: Path) -> None:
    experiment = work_root / "cflm"
    experiment.mkdir(parents=True)
    (experiment / "config.json").write_text(json.dumps({"workflow": "cflm", "device": "HPK-Si-PiN"}))

    with pytest.raises(SystemExit, match="has no analysis slice"):
        main(["ana", str(experiment)])


def test_gen_takes_the_place_of_the_events_a_job_records_and_both_at_once_are_refused(
    work_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(jobs, "run_indexed_jobs", lambda *a, **k: None)

    assert main(["dep", "HPK-Si-PiN", "-gen", "30", "--seed", "1", "-s", "2"]) == 0

    options = json.loads((work_root / "HPK-Si-PiN" / "signal" / "seed_1" / "run.json").read_text())["options"]
    assert options["generated_per_job"] == 30 and "events_per_job" not in options
    with pytest.raises(ValueError, match="events_per_job and generated_per_job are given at once"):
        main(["dep", "HPK-Si-PiN", "-gen", "30", "-evt", "5", "--seed", "2", "-s", "2"])
