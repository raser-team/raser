from __future__ import annotations

import argparse
import errno
import json
import os
import shutil
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from raser.lifecycle import jobs
from raser.lifecycle import workflow as workflow_module
from raser.lifecycle.slices import Slice
from raser.lifecycle.workflow import Workflow
from raser.lifecycle.workflow import execute


@pytest.fixture
def started(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    """The job commands handed to the local pool or the cluster; they finish."""
    monkeypatch.setenv("RASER_WORK_PATH", str(tmp_path))
    monkeypatch.delenv("RASER_PROJECT_PATH", raising=False)
    monkeypatch.chdir(tmp_path)
    calls: list[Any] = []

    def run_indexed_jobs(prefix, tail, count, *, indices, **options):
        calls.append((prefix, tail, list(indices), options["use_cluster"]))
        for index in indices:
            (Path(tail[-1]) / "batch" / f"job_{index}.done").touch()

    def own_process(workflow, kwargs, words):
        workflow_module._run_job(workflow, {**kwargs, "job_dir": words[-1]})

    monkeypatch.setattr(jobs, "run_indexed_jobs", run_indexed_jobs)
    monkeypatch.setattr(workflow_module, "_own_process", own_process)
    monkeypatch.setattr(workflow_module, "_commit", lambda: "abc")
    return calls


@pytest.fixture
def seeded(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """The seeds given to the generators, without loading ROOT."""
    seeds: list[int] = []
    seeding = SimpleNamespace(seed_generators=seeds.append)
    monkeypatch.setitem(sys.modules, "raser.core.seeding", seeding)
    return seeds


def _kwargs(**given: Any) -> dict[str, Any]:
    kwargs: dict[str, Any]
    kwargs = {"jobs": None, "batch": False, "mem": 1, "seed": 42, "dry_run": False}
    kwargs.update(scan=[], same_seeds=False, _entry_command_prefix=("toy",))
    return {**kwargs, **given}


TOY = Workflow(name="toy", job=lambda options: None, device=False)


def test_s_starts_that_many_jobs_of_the_same_command_in_the_seed_folder(
    started: list[Any], disk: dict[str, Any], tmp_path: Path
) -> None:
    workflow = Workflow(
        name="toy run", job=lambda options: None, command=lambda kwargs: ["--fast"]
    )

    execute(workflow, _kwargs(det_name="dev", jobs=3))

    folder = tmp_path / "toy" / "run" / "seed_42"
    tail = ["run", "dev", "--fast", "--job-dir", str(folder)]
    assert started == [(("toy",), tail, [0, 1, 2], False)]
    assert json.loads((folder / "run.json").read_text())["seed"] == 42


def test_without_s_the_single_job_runs_in_this_process_without_a_job_index(
    started: list[Any], seeded: list[int], tmp_path: Path
) -> None:
    received: list[dict[str, Any]] = []
    workflow = Workflow(name="toy", job=received.append, device=False)

    execute(workflow, _kwargs())
    execute(workflow, _kwargs())  # finished: nothing is left to run

    assert started == []
    assert len(received) == 1
    assert received[0].get("job_index") is None
    assert received[0]["_run_batch_path"] == str(tmp_path / "toy" / "seed_42" / "batch")
    assert seeded == [received[0]["seed"]]


def test_b_without_s_submits_the_single_job_to_the_cluster(started: list[Any]) -> None:
    execute(TOY, _kwargs(batch=True))

    assert [(indices, cluster) for _, _, indices, cluster in started] == [([0], True)]


def test_the_same_fixed_seed_again_starts_only_the_jobs_that_did_not_finish(
    started: list[Any],
) -> None:
    execute(TOY, _kwargs(jobs=2))
    execute(TOY, _kwargs(jobs=2))
    execute(TOY, _kwargs(jobs=4))

    assert [indices for _, _, indices, _ in started] == [[0, 1], [2, 3]]


def test_without_a_seed_the_folder_is_a_timestamp_and_the_drawn_seed_is_recorded(
    started: list[Any], tmp_path: Path
) -> None:
    execute(TOY, _kwargs(seed=None, jobs=2))

    (folder,) = (path for path in (tmp_path / "toy").iterdir() if path.is_dir())
    assert not folder.name.startswith("seed_")
    assert isinstance(json.loads((folder / "run.json").read_text())["seed"], int)


def test_job_seeds_differ_within_a_run_repeat_exactly_and_do_not_overlap_between_runs(
    started: list[Any], seeded: list[int], tmp_path: Path
) -> None:
    def seeds_of(run_seed: int) -> list[int]:
        execute(TOY, _kwargs(seed=run_seed, jobs=2))
        folder = str(tmp_path / "toy" / f"seed_{run_seed}")
        seeded.clear()
        for index in (0, 1):
            execute(TOY, _kwargs(job_dir=folder, job_index=index))
        return list(seeded)

    first, again, neighbour = seeds_of(42), seeds_of(42), seeds_of(43)

    assert first[0] != first[1]
    assert again == first
    assert not set(first) & set(neighbour)
    assert all(0 < seed < 2**31 for seed in first)


def test_dry_run_prints_the_seed_folder_and_its_jobs_and_writes_nothing(
    started: list[Any], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    execute(TOY, _kwargs(jobs=2, dry_run=True))

    assert capsys.readouterr().out == f"{tmp_path / 'toy' / 'seed_42'}: jobs [0, 1]\n"
    assert started == []
    assert not (tmp_path / "toy").exists()


GAIN = Workflow(
    name="toy",
    job=lambda options: None,
    keys=("gain", "width"),
    defaults={"gain": 5, "width": 1.0},
    device=False,
)


def _options(folder: Path) -> dict[str, Any]:
    return json.loads((folder / "run.json").read_text())["options"]


def test_options_are_the_defaults_then_the_config_then_the_command_line(
    started: list[Any], tmp_path: Path
) -> None:
    experiment = tmp_path / "toy"
    experiment.mkdir()
    config = {"workflow": "toy", "set": {"gain": 7, "width": 2.0}}
    (experiment / "config.json").write_text(json.dumps(config))

    execute(GAIN, _kwargs(gain=None, width=None, seed=1))
    execute(GAIN, _kwargs(gain=9, width=None, seed=2, jobs=2))

    assert _options(experiment / "seed_1") == {"gain": 7, "width": 2.0}
    assert _options(experiment / "seed_2") == {"gain": 9, "width": 2.0}


def test_the_first_run_writes_the_config_and_later_runs_follow_it(
    started: list[Any], tmp_path: Path
) -> None:
    execute(GAIN, _kwargs(gain=9, width=None, seed=1, jobs=2))
    execute(GAIN, _kwargs(gain=None, width=None, seed=2, jobs=2))

    config = json.loads((tmp_path / "toy" / "config.json").read_text())
    assert config == {
        "workflow": "toy",
        "set": {"gain": 9},
        "scan": {},
        "same_seeds": False,
    }
    assert _options(tmp_path / "toy" / "seed_2") == {"gain": 9, "width": 1.0}


def test_a_job_receives_the_options_recorded_in_its_seed_folder(
    started: list[Any], seeded: list[int], tmp_path: Path
) -> None:
    received: list[dict[str, Any]] = []
    workflow = Workflow(
        name="toy",
        job=received.append,
        keys=("gain",),
        defaults={"gain": 5},
        device=False,
    )
    execute(workflow, _kwargs(gain=9, jobs=2))

    folder = str(tmp_path / "toy" / "seed_42")
    execute(workflow, _kwargs(gain=None, job_dir=folder, job_index=1))

    assert received[0]["gain"] == 9


def test_a_config_here_for_this_command_makes_this_folder_the_experiment(
    started: list[Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mine, other = tmp_path / "mine", tmp_path / "other"
    for folder, name in ((mine, "toy"), (other, "something else")):
        folder.mkdir()
        (folder / "config.json").write_text(json.dumps({"workflow": name}))

    monkeypatch.chdir(mine)
    execute(GAIN, _kwargs(gain=None, width=None, jobs=2))
    monkeypatch.chdir(other)
    execute(GAIN, _kwargs(gain=None, width=None, jobs=2))

    assert (mine / "seed_42" / "run.json").is_file()
    assert not (other / "seed_42").exists()
    assert (other / "toy" / "seed_42" / "run.json").is_file()


@pytest.fixture
def disk(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """The json files on disk: a device and components, named by kind and selector."""
    content: dict[str, Any] = {"marker": "first"}

    def load_component(kind: str, selector: str) -> tuple[Path, dict[str, Any]]:
        return Path(f"{selector}.json"), {"kind": kind, "selector": selector, **content}

    def device_json(selector: str) -> dict[str, Any]:
        bias = {"electrode": "top", "voltage": 200.0}
        return {"det_name": selector, "bias": bias, **content}

    monkeypatch.setattr(workflow_module, "load_component", load_component)
    monkeypatch.setattr(workflow_module, "device_json", device_json)
    return content


def test_run_json_holds_the_device_file_and_the_files_the_options_name(
    started: list[Any], disk: dict[str, Any], tmp_path: Path
) -> None:
    workflow = Workflow(
        name="toy",
        job=lambda options: None,
        keys=("amplifier",),
        defaults={"amplifier": "standard"},
        components={"afe": "amplifier"},
    )

    execute(workflow, _kwargs(det_name="dev", amplifier="fast", jobs=2))

    files = json.loads((tmp_path / "toy" / "seed_42" / "run.json").read_text())["files"]
    assert files == {
        "device": {
            "det_name": "dev",
            "bias": {"electrode": "top", "voltage": 200.0},
            "marker": "first",
        },
        "afe": {"kind": "afe", "selector": "fast", "marker": "first"},
    }


def test_a_job_reads_its_files_from_run_json_and_not_from_disk(
    started: list[Any], seeded: list[int], disk: dict[str, Any], tmp_path: Path
) -> None:
    received: list[dict[str, Any]] = []
    workflow = Workflow(
        name="toy",
        job=received.append,
        keys=("amplifier",),
        defaults={"amplifier": "standard"},
        components={"afe": "amplifier"},
        device=False,
    )
    execute(workflow, _kwargs(amplifier=None, jobs=2))
    disk["marker"] = "edited after the run was created"

    folder = str(tmp_path / "toy" / "seed_42")
    execute(workflow, _kwargs(amplifier=None, job_dir=folder, job_index=0))

    assert received[0]["_files"] == {
        "afe": {"kind": "afe", "selector": "standard", "marker": "first"}
    }


TOY_DEVICE = Workflow(name="toy", job=lambda options: None)

BIASED = Workflow(
    name="toy",
    job=lambda options: None,
    keys=("voltage",),
    in_file={"voltage": "device.bias.voltage"},
)


def _record(folder: Path) -> dict[str, Any]:
    return json.loads((folder / "run.json").read_text())


def test_an_option_that_sits_in_a_file_takes_the_value_of_the_file_when_not_given(
    started: list[Any], disk: dict[str, Any], tmp_path: Path
) -> None:
    execute(BIASED, _kwargs(det_name="dev", voltage=None, jobs=2))

    record = _record(tmp_path / "toy" / "seed_42")
    assert record["options"]["voltage"] == 200.0
    assert record["files"]["device"]["bias"]["voltage"] == 200.0


def test_an_option_that_sits_in_a_file_is_written_into_the_recorded_file_when_given(
    started: list[Any], disk: dict[str, Any], tmp_path: Path
) -> None:
    execute(BIASED, _kwargs(det_name="dev", voltage=300.0, jobs=2))

    record = _record(tmp_path / "toy" / "seed_42")
    assert record["options"]["voltage"] == 300.0
    assert record["files"]["device"]["bias"] == {"electrode": "top", "voltage": 300.0}


def _folders(started: list[Any], experiment: Path) -> list[str]:
    return [str(Path(tail[-1]).relative_to(experiment)) for _, tail, _, _ in started]


def test_a_scan_runs_every_value_and_every_value_gets_a_folder_named_by_the_scanned_key(
    started: list[Any], disk: dict[str, Any], tmp_path: Path
) -> None:
    scan = ["voltage=200,300"]

    execute(BIASED, _kwargs(det_name="dev", voltage=None, scan=scan, jobs=2))

    experiment = tmp_path / "toy"
    assert _folders(started, experiment) == ["voltage_200/seed_42", "voltage_300/seed_42"]
    assert _record(experiment / "voltage_200" / "seed_42")["options"]["voltage"] == 200
    assert _record(experiment / "voltage_300" / "seed_42")["options"]["voltage"] == 300


def test_a_scanned_address_is_written_into_the_file_of_each_point(
    started: list[Any], disk: dict[str, Any], tmp_path: Path
) -> None:
    scan = ["device.bias.voltage=200,300"]

    execute(TOY_DEVICE, _kwargs(det_name="dev", scan=scan, jobs=2))

    experiment = tmp_path / "toy"
    assert _folders(started, experiment) == ["bias.voltage_200/seed_42", "bias.voltage_300/seed_42"]
    unscanned = _record(experiment / "bias.voltage_200" / "seed_42")
    scanned = _record(experiment / "bias.voltage_300" / "seed_42")
    assert unscanned["files"]["device"]["bias"] == {"electrode": "top", "voltage": 200.0}
    assert scanned["files"]["device"]["bias"] == {"electrode": "top", "voltage": 300}
    assert scanned["options"]["device.bias.voltage"] == 300


@pytest.mark.parametrize("where", ["command line", "config"])
def test_a_name_the_config_gives_an_address_names_the_folders_and_may_be_scanned(
    started: list[Any], disk: dict[str, Any], tmp_path: Path, where: str
) -> None:
    experiment = tmp_path / "toy"
    experiment.mkdir()
    config: dict[str, Any]
    config = {"workflow": "toy", "device": "dev", "names": {"device.bias.voltage": "bias"}}
    if where == "config":
        config["scan"] = {"bias": [200, 300]}
    (experiment / "config.json").write_text(json.dumps(config))
    scan = ["bias=200,300"] if where == "command line" else []

    execute(TOY_DEVICE, _kwargs(det_name="dev", scan=scan, jobs=2))

    assert _folders(started, experiment) == ["bias_200/seed_42", "bias_300/seed_42"]
    scanned = _record(experiment / "bias_300" / "seed_42")
    assert scanned["files"]["device"]["bias"]["voltage"] == 300
    assert scanned["options"]["device.bias.voltage"] == 300


def test_two_scanned_addresses_that_end_alike_stop_the_command_until_one_is_named(
    started: list[Any], disk: dict[str, Any], tmp_path: Path
) -> None:
    disk["spare"] = {"bias": {"voltage": 1.0}}
    scan = ["device.bias.voltage=200,300", "device.spare.bias.voltage=1,2"]

    with pytest.raises(ValueError, match="would both be 'bias.voltage'"):
        execute(TOY_DEVICE, _kwargs(det_name="dev", scan=scan, jobs=2))
    assert started == []

    experiment = tmp_path / "toy"
    experiment.mkdir()
    config = {"workflow": "toy", "device": "dev", "names": {"device.spare.bias.voltage": "spare"}}
    (experiment / "config.json").write_text(json.dumps(config))
    execute(TOY_DEVICE, _kwargs(det_name="dev", scan=scan, jobs=2))

    assert _folders(started, experiment) == [
        "bias.voltage_200_spare_1/seed_42",
        "bias.voltage_200_spare_2/seed_42",
        "bias.voltage_300_spare_1/seed_42",
        "bias.voltage_300_spare_2/seed_42",
    ]


@pytest.mark.parametrize(
    ("address", "broken"),
    [
        ("afe.gain", "no 'afe' in the files of this run"),
        ("device.bais.voltage", "no 'bais' in device"),
        ("device.bias.volt", "no 'volt' in device.bias"),
        ("device.bias.voltage.unit", "no 'unit' in device.bias.voltage"),
        ("device.bias.voltage.unit.name", "no 'unit' in device.bias.voltage"),
    ],
)
def test_an_address_that_leads_nowhere_stops_the_command_and_says_where(
    started: list[Any], disk: dict[str, Any], tmp_path: Path, address: str, broken: str
) -> None:
    with pytest.raises(ValueError, match=broken):
        execute(TOY_DEVICE, _kwargs(det_name="dev", scan=[f"{address}=1,2"], jobs=2))

    assert started == []
    assert not (tmp_path / "toy").exists()


def test_two_scanned_options_give_every_combination_named_by_both_keys(
    started: list[Any], tmp_path: Path
) -> None:
    scan = ["gain=5,7", "width=1.0,2.0"]

    execute(GAIN, _kwargs(gain=None, width=None, scan=scan, jobs=2))

    assert _folders(started, tmp_path / "toy") == [
        "gain_5_width_1/seed_42",
        "gain_5_width_2/seed_42",
        "gain_7_width_1/seed_42",
        "gain_7_width_2/seed_42",
    ]


def test_two_combinations_that_would_name_one_folder_stop_the_command_before_any_job(
    started: list[Any], tmp_path: Path
) -> None:
    scan = ["gain=5_width_1,5", "width=2,1_width_2"]

    with pytest.raises(ValueError, match="gain_5_width_1_width_2"):
        execute(GAIN, _kwargs(gain=None, width=None, scan=scan, jobs=2))

    assert started == []
    assert not (tmp_path / "toy").exists()


def test_a_value_given_for_an_option_the_config_scans_runs_only_that_value(
    started: list[Any], tmp_path: Path
) -> None:
    experiment = tmp_path / "toy"
    experiment.mkdir()
    config = {"workflow": "toy", "scan": {"gain": [5, 7]}}
    (experiment / "config.json").write_text(json.dumps(config))

    execute(GAIN, _kwargs(gain=9, width=None, jobs=2))

    assert _folders(started, experiment) == ["seed_42"]
    assert _options(experiment / "seed_42")["gain"] == 9


def test_the_first_run_writes_its_scan_to_the_config_and_later_runs_repeat_it(
    started: list[Any], tmp_path: Path
) -> None:
    execute(GAIN, _kwargs(gain=None, width=None, scan=["gain=5,7"], seed=1, jobs=2))
    execute(GAIN, _kwargs(gain=None, width=None, seed=2, jobs=2))

    assert _folders(started, tmp_path / "toy") == [
        "gain_5/seed_1",
        "gain_7/seed_1",
        "gain_5/seed_2",
        "gain_7/seed_2",
    ]


def test_a_scan_given_once_the_experiment_exists_joins_its_config(
    started: list[Any], tmp_path: Path
) -> None:
    experiment = tmp_path / "toy"
    experiment.mkdir()
    config = {"workflow": "toy", "set": {}, "scan": {"width": [1.0, 2.0]}}
    (experiment / "config.json").write_text(json.dumps(config))

    execute(GAIN, _kwargs(gain=None, width=None, scan=["gain=5,7"], seed=1, jobs=2))
    execute(GAIN, _kwargs(gain=None, width=None, seed=2, jobs=2))

    written = json.loads((experiment / "config.json").read_text())
    assert written["scan"] == {"width": [1.0, 2.0], "gain": [5, 7]}
    assert "width_2_gain_7/seed_2" in _folders(started, experiment)


def test_a_later_scan_by_short_name_or_address_leaves_one_entry_and_the_last_values(
    started: list[Any], tmp_path: Path
) -> None:
    experiment = tmp_path / "toy"
    experiment.mkdir()
    config = {"workflow": "toy", "set": {}, "scan": {"g": [5, 7]}, "names": {"gain": "g"}}
    (experiment / "config.json").write_text(json.dumps(config))

    execute(GAIN, _kwargs(gain=None, width=None, scan=["gain=8,9"], seed=1, jobs=2))
    execute(GAIN, _kwargs(gain=None, width=None, scan=["g=6,7"], seed=2, jobs=2))
    started.clear()
    execute(GAIN, _kwargs(gain=None, width=None, seed=3, jobs=2))

    assert json.loads((experiment / "config.json").read_text())["scan"] == {"gain": [6, 7]}
    assert _folders(started, experiment) == ["g_6/seed_3", "g_7/seed_3"]


def test_an_option_without_a_default_can_be_scanned_and_every_value_gets_a_folder(
    started: list[Any], tmp_path: Path
) -> None:
    workflow = replace(GAIN, defaults={"width": 1.0})

    execute(workflow, _kwargs(gain=None, width=None, scan=["gain=5,7"], jobs=2))

    assert _folders(started, tmp_path / "toy") == ["gain_5/seed_42", "gain_7/seed_42"]


def _kept(experiment: Path) -> list[Path]:
    return sorted(experiment.glob("seed_42_*"))


def test_a_fixed_seed_given_other_options_runs_again_and_keeps_the_old_run(
    started: list[Any], tmp_path: Path
) -> None:
    execute(GAIN, _kwargs(gain=5, width=None, jobs=2))
    execute(GAIN, _kwargs(gain=7, width=None, jobs=2))

    experiment = tmp_path / "toy"
    assert [indices for _, _, indices, _ in started] == [[0, 1], [0, 1]]
    (kept,) = _kept(experiment)
    assert _options(kept)["gain"] == 5
    assert (kept / "batch" / "job_0.done").is_file()
    assert _options(experiment / "seed_42")["gain"] == 7


def test_a_fixed_seed_runs_again_when_a_file_it_uses_changed(
    started: list[Any], disk: dict[str, Any], tmp_path: Path
) -> None:
    execute(BIASED, _kwargs(det_name="dev", voltage=None, jobs=2))
    disk["marker"] = "edited"
    execute(BIASED, _kwargs(det_name="dev", voltage=None, jobs=2))

    assert [indices for _, _, indices, _ in started] == [[0, 1], [0, 1]]
    assert len(_kept(tmp_path / "toy")) == 1


@pytest.mark.parametrize(
    ("first", "second"), [("abc", "def"), ("abc+dirty", "abc+dirty")]
)
def test_a_fixed_seed_runs_again_under_another_commit_or_uncommitted_changes(
    started: list[Any],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    first: str,
    second: str,
) -> None:
    monkeypatch.setattr(workflow_module, "_commit", lambda: first)
    execute(GAIN, _kwargs(gain=None, width=None, jobs=2))
    monkeypatch.setattr(workflow_module, "_commit", lambda: second)
    execute(GAIN, _kwargs(gain=None, width=None, jobs=2))

    assert [indices for _, _, indices, _ in started] == [[0, 1], [0, 1]]
    assert len(_kept(tmp_path / "toy")) == 1


def test_the_finished_jobs_of_a_folder_come_from_the_workflow_and_device_its_config_names(
    started: list[Any], disk: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    other = Workflow(name="other", job=lambda options: None, keys=("gain",), defaults={"gain": 5})
    monkeypatch.setattr(workflow_module, "WORKFLOWS", {})
    for workflow in (BIASED, other):
        workflow.attach(argparse.ArgumentParser())
    execute(BIASED, _kwargs(det_name="dev", voltage=None, scan=["voltage=200,300"], jobs=2))
    execute(other, _kwargs(det_name="dev", gain=None, jobs=1))

    points = workflow_module.finished_in(tmp_path / "toy")

    assert [(name, options["voltage"], [index for _, index in done]) for name, options, done in points] == [
        ("voltage_200", 200, [0, 1]),
        ("voltage_300", 300, [0, 1]),
    ]
    assert [(name, options, len(done)) for name, options, done in workflow_module.finished_in(tmp_path / "other")] == [
        ("", {"gain": 5}, 1)
    ]


def test_a_folder_that_is_no_experiment_or_whose_workflow_has_no_command_is_refused(
    started: list[Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(workflow_module, "WORKFLOWS", {})
    execute(GAIN, _kwargs(gain=None, width=None, jobs=2))

    with pytest.raises(ValueError, match="not an experiment folder"):
        workflow_module.finished_in(tmp_path / "toy" / "seed_42")
    with pytest.raises(ValueError, match="no command runs its workflow 'toy'"):
        workflow_module.finished_in(tmp_path / "toy")


def _finished(experiment: Path) -> list[tuple[str, int, list[str]]]:
    """Per point: its folder name, its gain, and the seed folders of its finished jobs."""
    points = workflow_module.finished(GAIN, _kwargs(), experiment)
    return [
        (name, options["gain"], [f"{folder.name}:{index}" for folder, index in done])
        for name, options, done in points
    ]


def test_finished_lists_every_point_with_the_jobs_of_all_its_seed_folders(
    started: list[Any], tmp_path: Path
) -> None:
    scan = ["gain=5,7"]
    execute(GAIN, _kwargs(gain=None, width=None, scan=scan, seed=1, jobs=2))
    execute(GAIN, _kwargs(gain=None, width=None, scan=scan, seed=2, jobs=1))

    assert _finished(tmp_path / "toy") == [
        ("gain_5", 5, ["seed_1:0", "seed_1:1", "seed_2:0"]),
        ("gain_7", 7, ["seed_1:0", "seed_1:1", "seed_2:0"]),
    ]


def test_finished_leaves_out_seed_folders_that_ran_with_other_options(
    started: list[Any], tmp_path: Path
) -> None:
    execute(GAIN, _kwargs(gain=None, width=None, seed=1, jobs=2))
    execute(GAIN, _kwargs(gain=None, width=2.0, seed=2, jobs=2))

    assert _finished(tmp_path / "toy") == [("", 5, ["seed_1:0", "seed_1:1"])]


def test_finished_leaves_out_a_folder_kept_aside_and_takes_any_commit(
    started: list[Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(workflow_module, "_commit", lambda: "abc+dirty")
    execute(GAIN, _kwargs(gain=None, width=None, seed=1, jobs=2))
    execute(GAIN, _kwargs(gain=None, width=None, seed=1, jobs=1))
    monkeypatch.setattr(workflow_module, "_commit", lambda: "def")
    execute(GAIN, _kwargs(gain=None, width=None, seed=2, jobs=1))

    assert _finished(tmp_path / "toy") == [("", 5, ["seed_1:0", "seed_2:0"])]


def _point_seeds(seeded: list[int], experiment: Path, **given: Any) -> list[list[int]]:
    """Job seeds of the two points of a gain scan, for job indices 0 and 1."""
    execute(GAIN, _kwargs(gain=None, width=None, scan=["gain=5,7"], jobs=2, **given))
    seeds = []
    for point in ("gain_5", "gain_7"):
        seeded.clear()
        for index in (0, 1):
            folder = str(experiment / point / "seed_42")
            execute(
                GAIN, _kwargs(gain=None, width=None, job_dir=folder, job_index=index)
            )
        seeds.append(list(seeded))
    return seeds


def test_points_draw_different_job_seeds_unless_same_seeds_is_given(
    started: list[Any], seeded: list[int], tmp_path: Path
) -> None:
    root, seven = _point_seeds(seeded, tmp_path / "toy")
    assert not set(root) & set(seven)

    root, seven = _point_seeds(seeded, tmp_path / "toy", same_seeds=True)
    assert root == seven
    assert root[0] != root[1]


def test_same_seeds_in_the_config_holds_without_the_option(
    started: list[Any], seeded: list[int], tmp_path: Path
) -> None:
    experiment = tmp_path / "toy"
    experiment.mkdir()
    (experiment / "config.json").write_text(
        json.dumps({"workflow": "toy", "same_seeds": True})
    )

    root, seven = _point_seeds(seeded, experiment)

    assert root == seven


def _plain(**given: Any) -> dict[str, Any]:
    """The options of a command of a workflow without seeds."""
    kwargs: dict[str, Any] = {"batch": False, "mem": 1, "dry_run": False, "scan": []}
    return {**kwargs, "_entry_command_prefix": ("toy",), **given}


def test_without_seeds_the_job_of_every_point_runs_in_the_point_folder_at_every_command(
    started: list[Any], tmp_path: Path
) -> None:
    received: list[dict[str, Any]] = []
    workflow = Workflow(
        name="toy", job=received.append, keys=("x",), defaults={"x": 1},
        device=False, seeds=False,
    )

    execute(workflow, _plain(scan=["x=1,2"]))
    execute(workflow, _plain(scan=["x=1,2"]))

    experiment = tmp_path / "toy"
    assert [options["_run_path"] for options in received] == [
        str(experiment / "x_1"),
        str(experiment / "x_2"),
    ] * 2
    assert "seed" not in received[0]
    assert _record(experiment / "x_2") == {
        "point": "x_2", "commit": "abc", "options": {"x": 2}, "files": {}, "jobs": 1,
    }
    assert "same_seeds" not in json.loads((experiment / "config.json").read_text())
    assert [(name, len(done)) for name, _, done in
            workflow_module.finished(workflow, _plain(), experiment)] == [("x_1", 1), ("x_2", 1)]


def test_a_workflow_that_names_its_folder_has_its_experiment_there_wherever_the_command_is_run(
    started: list[Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    received: list[dict[str, Any]] = []
    workflow = Workflow(
        name="toy", job=received.append, keys=("x",), defaults={"x": 1},
        device=False, seeds=False, folder=lambda kwargs: Path(kwargs["inside"]) / "toy",
    )
    here = tmp_path / "another toy"
    here.mkdir()
    (here / "config.json").write_text(json.dumps({"workflow": "toy", "set": {"x": 5}}))
    monkeypatch.chdir(here)

    execute(workflow, _plain(inside=str(tmp_path / "first")))
    execute(workflow, _plain(inside=str(tmp_path / "second"), x=2))

    assert [(options["_run_path"], options["x"]) for options in received] == [
        (str(tmp_path / "first" / "toy"), 1),
        (str(tmp_path / "second" / "toy"), 2),
    ]
    assert json.loads((tmp_path / "second" / "toy" / "config.json").read_text())["set"] == {"x": 2}


def test_without_seeds_a_point_run_with_another_record_is_run_again_in_its_place(
    started: list[Any], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    def job(options: dict[str, Any]) -> None:
        if options["x"] == 5:
            raise RuntimeError("the second run fails")

    workflow = Workflow(
        name="toy", job=job, keys=("x",), defaults={"x": 1}, device=False, seeds=False
    )
    execute(workflow, _plain())

    with pytest.raises(RuntimeError):
        execute(workflow, _plain(x=5))

    experiment = tmp_path / "toy"
    assert "the old run is replaced" in capsys.readouterr().out
    assert _record(experiment)["options"] == {"x": 5}
    assert sorted(path.name for path in tmp_path.iterdir() if not path.name.startswith(".")) == ["toy"]
    assert not (experiment / "batch" / "job_0.done").exists()


def _other_options(old: dict[str, Any], record: dict[str, Any]) -> str | None:
    """Only the options make a run out of date; the old record may hold more."""
    return None if old["options"] == record["options"] else "x changed"


def test_what_a_job_wrote_into_run_json_stays_until_the_workflow_says_the_run_is_out_of_date(
    started: list[Any],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    experiment = tmp_path / "toy"
    seen: list[Any] = []

    def job(options: dict[str, Any]) -> None:
        record = _record(experiment)
        seen.append(record.get("written by the job"))
        (experiment / "run.json").write_text(
            json.dumps({**record, "written by the job": options["x"]})
        )

    workflow = Workflow(
        name="toy", job=job, keys=("x",), defaults={"x": 1}, device=False, seeds=False
    )
    execute(workflow, _plain())
    execute(workflow, _plain())  # the rule of the lifecycle: what the job wrote does not count
    assert seen == [None, 1]

    workflow = Workflow(
        name="toy", job=job, keys=("x",), defaults={"x": 1},
        device=False, seeds=False, outdated=_other_options,
    )
    monkeypatch.setattr(workflow_module, "_commit", lambda: "def+dirty")
    execute(workflow, _plain())
    assert seen == [None, 1, 1]
    assert _record(experiment)["commit"] == "def+dirty"
    assert [len(done) for _, _, done in
            workflow_module.finished(workflow, _plain(), experiment)] == [1]

    execute(workflow, _plain(x=5))
    assert seen == [None, 1, 1, None]
    assert "the old run is replaced: x changed" in capsys.readouterr().out


def test_without_seeds_a_point_whose_folder_begins_with_seed_counts_as_finished(
    started: list[Any], tmp_path: Path
) -> None:
    workflow = Workflow(
        name="toy", job=lambda options: None, keys=("seed_layer",),
        defaults={"seed_layer": 1}, device=False, seeds=False,
    )

    execute(workflow, _plain(scan=["seed_layer=1,2"]))

    points = workflow_module.finished(workflow, _plain(), tmp_path / "toy")
    assert [(name, len(done)) for name, _, done in points] == [("seed_layer_1", 1), ("seed_layer_2", 1)]


def test_each_of_several_points_runs_in_a_process_of_its_own_and_one_failing_leaves_the_rest(
    started: list[Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ran: list[int] = []
    commands: list[list[str]] = []

    def job(options: dict[str, Any]) -> None:
        ran.append(options["x"])
        if options["x"] == 2:
            raise RuntimeError("no field at this bias")

    workflow = Workflow(
        name="toy", job=job, keys=("x",), defaults={"x": 1}, device=False, seeds=False
    )

    def own_process(workflow, kwargs, words: list[str]) -> None:
        """What the command `words` does in its process, and how it ends there."""
        commands.append(words)
        try:
            execute(workflow, _plain(job_dir=words[-1]))
        except RuntimeError as error:
            raise workflow_module.subprocess.CalledProcessError(1, words) from error

    monkeypatch.setattr(workflow_module, "_own_process", own_process)
    experiment = tmp_path / "toy"

    with pytest.raises(SystemExit) as stopped:
        execute(workflow, _plain(scan=["x=1,2,3"]))

    assert ran == [1, 2, 3]
    assert commands == [
        ["toy", "--job-dir", str(experiment / name)] for name in ("x_1", "x_2", "x_3")
    ]
    assert "1 of 3 points failed" in str(stopped.value)
    assert str(experiment / "x_2") in str(stopped.value)
    assert [len(done) for _, _, done in
            workflow_module.finished(workflow, _plain(), experiment)] == [1, 0, 1]

    commands.clear()
    with pytest.raises(RuntimeError, match="no field at this bias"):
        execute(workflow, _plain(x=2))
    assert commands == []


@pytest.fixture
def ran() -> list[tuple[str, Any]]:
    """What the slices of CHAIN ran: (slice, the value of its own option)."""
    return []


def _chain(ran: list[tuple[str, Any]], fail: str | None = None) -> Workflow:
    """A job of three slices: the source, then the bias written into the device, then the amplifier."""

    def piece(name: str, key: str) -> Slice:
        def run(options: dict[str, Any]) -> None:
            if name == fail:
                raise RuntimeError(name)
            ran.append((name, options[key]))

        last = key == "amplifier"  # the electronics: it reads its file, and measures nothing
        return Slice(name, run, keys=(key,), kinds=("afe",) if last else (), new_events=not last)

    return Workflow(
        name="toy",
        slices=(piece("deposits", "source"), piece("currents", "voltage"), piece("waveforms", "amplifier")),
        keys=("source", "voltage", "amplifier"),
        defaults={"source": "beta", "amplifier": "standard"},
        components={"afe": "amplifier"},
        in_file={"voltage": "device.bias.voltage"},
    )


def _chain_kwargs(**given: Any) -> dict[str, Any]:
    options = {"det_name": "dev", "source": None, "voltage": None, "amplifier": None, "until": None}
    return _kwargs(**{**options, **given})


def test_a_job_runs_its_slices_in_order_and_a_second_command_runs_none_again(
    started: list[Any], seeded: list[int], disk: dict[str, Any], ran: list[tuple[str, Any]]
) -> None:
    execute(_chain(ran), _chain_kwargs())
    execute(_chain(ran), _chain_kwargs())

    assert ran == [("deposits", "beta"), ("currents", 200.0), ("waveforms", "standard")]


@pytest.mark.parametrize(
    ("changed", "again"),
    [
        ({"amplifier": "fast"}, [("waveforms", "fast")]),
        ({"voltage": 300.0}, [("currents", 300.0), ("waveforms", "standard")]),
    ],
)
def test_an_option_of_a_later_slice_runs_that_slice_and_the_ones_after_it_again_in_place(
    started: list[Any],
    seeded: list[int],
    disk: dict[str, Any],
    ran: list[tuple[str, Any]],
    tmp_path: Path,
    changed: dict[str, Any],
    again: list[tuple[str, Any]],
) -> None:
    execute(_chain(ran), _chain_kwargs())
    del ran[:]

    execute(_chain(ran), _chain_kwargs(**changed))

    assert ran == again
    assert _kept(tmp_path / "toy") == []
    (key, value), = changed.items()
    assert _record(tmp_path / "toy" / "seed_42")["options"][key] == value


@pytest.mark.parametrize("changed", [{"amplifier": "other"}, {"source": "alpha"}])
def test_a_change_to_a_seed_folder_whose_job_runs_is_refused_and_leaves_it_as_it_was(
    started: list[Any],
    seeded: list[int],
    disk: dict[str, Any],
    ran: list[tuple[str, Any]],
    tmp_path: Path,
    changed: dict[str, Any],
) -> None:
    execute(_chain(ran), _chain_kwargs())
    folder = tmp_path / "toy" / "seed_42"
    before = (folder / "run.json").read_text()
    marks = sorted(path.name for path in (folder / "batch").glob("*.done"))
    del ran[:]
    held = workflow_module._lock(folder / "batch" / "job_0.lock", "job 0")  # job 0 runs

    with pytest.raises(SystemExit) as stopped:
        execute(_chain(ran), _chain_kwargs(**changed))
    held.close()

    assert stopped.value.code not in (0, None)
    assert f"{folder}" in str(stopped.value) and "did not take effect" in str(stopped.value)
    assert ran == [] and _kept(tmp_path / "toy") == []
    assert (folder / "run.json").read_text() == before
    assert sorted(path.name for path in (folder / "batch").glob("*.done")) == marks


def test_a_job_whose_run_json_changed_while_it_ran_has_no_mark_and_its_node_is_of_what_it_read(
    started: list[Any], seeded: list[int], disk: dict[str, Any], tmp_path: Path
) -> None:
    folder = tmp_path / "toy" / "seed_42"

    def waveforms(options: dict[str, Any]) -> None:
        (Path(options["_node_paths"]["waveforms"]) / "waveforms.h5").write_text("made with the old amplifier")
        record = json.loads((folder / "run.json").read_text())
        record["options"]["amplifier"] = "other"  # another command, meanwhile
        (folder / "run.json").write_text(json.dumps(record))

    chain = _chain([])
    workflow = replace(chain, slices=(*chain.slices[:2], replace(chain.slices[2], run=waveforms)))

    with pytest.raises(RuntimeError, match="run.json changed"):
        execute(workflow, _chain_kwargs())

    assert not (folder / "batch" / "waveforms_0.done").exists()
    assert (folder / "batch" / "currents_0.done").exists()
    (node,) = (tmp_path / "toy" / "nodes" / "waveforms").glob("*/node.json")
    assert json.loads(node.read_text())["inputs"]["settings"]["amplifier"] == "standard"
    assert (node.parent / "waveforms.h5").read_text() == "made with the old amplifier"


def test_an_option_of_the_first_slice_runs_the_whole_job_again_and_keeps_the_old_run(
    started: list[Any], seeded: list[int], disk: dict[str, Any], ran: list[tuple[str, Any]], tmp_path: Path
) -> None:
    execute(_chain(ran), _chain_kwargs())
    del ran[:]

    execute(_chain(ran), _chain_kwargs(source="alpha"))

    assert ran == [("deposits", "alpha"), ("currents", 200.0), ("waveforms", "standard")]
    assert len(_kept(tmp_path / "toy")) == 1


def test_a_file_only_a_later_slice_reads_does_not_run_the_earlier_slices_again(
    started: list[Any], seeded: list[int], disk: dict[str, Any], ran: list[tuple[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    execute(_chain(ran), _chain_kwargs())
    del ran[:]
    loaded = workflow_module.load_component
    monkeypatch.setattr(
        workflow_module, "load_component", lambda kind, name: (loaded(kind, name)[0], {"edited": kind})
    )

    execute(_chain(ran), _chain_kwargs())

    assert ran == [("waveforms", "standard")]


def test_until_stops_after_a_slice_and_the_next_command_goes_on_from_there(
    started: list[Any], seeded: list[int], disk: dict[str, Any], ran: list[tuple[str, Any]], tmp_path: Path
) -> None:
    execute(_chain(ran), _chain_kwargs(until="currents"))

    assert ran == [("deposits", "beta"), ("currents", 200.0)]
    assert not (tmp_path / "toy" / "seed_42" / "batch" / "job_0.done").exists()

    execute(_chain(ran), _chain_kwargs())

    assert ran[2:] == [("waveforms", "standard")]
    assert (tmp_path / "toy" / "seed_42" / "batch" / "job_0.done").exists()


def test_a_slice_that_fails_leaves_the_ones_before_it_done(
    started: list[Any], seeded: list[int], disk: dict[str, Any], ran: list[tuple[str, Any]]
) -> None:
    with pytest.raises(RuntimeError, match="currents"):
        execute(_chain(ran, fail="currents"), _chain_kwargs())

    execute(_chain(ran), _chain_kwargs())

    assert ran == [("deposits", "beta"), ("currents", 200.0), ("waveforms", "standard")]


def test_until_twice_leaves_no_job_to_start_and_does_not_list_the_later_slices(
    started: list[Any],
    seeded: list[int],
    disk: dict[str, Any],
    ran: list[tuple[str, Any]],
    capsys: pytest.CaptureFixture[str],
) -> None:
    execute(_chain(ran), _chain_kwargs(until="currents"))
    capsys.readouterr()

    execute(_chain(ran), _chain_kwargs(until="currents"))

    lines = capsys.readouterr().out.splitlines()
    assert lines[0].endswith("seed_42: jobs []")
    assert [line.split() for line in lines[1:]] == [["deposits", "reused"], ["currents", "reused"]]


def test_under_another_commit_no_slice_runs_again_and_a_note_tells_it(
    started: list[Any],
    seeded: list[int],
    disk: dict[str, Any],
    ran: list[tuple[str, Any]],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    execute(_chain(ran), _chain_kwargs())
    del ran[:]
    monkeypatch.setattr(workflow_module, "_commit", lambda: "def+dirty")

    execute(_chain(ran), _chain_kwargs())

    assert ran == [] and _kept(tmp_path / "toy") == []
    assert "was run by abc, the code is def+dirty now" in capsys.readouterr().out


def test_without_seeds_a_run_out_of_date_runs_every_slice_again_in_its_folder(
    started: list[Any], disk: dict[str, Any], ran: list[tuple[str, Any]], tmp_path: Path
) -> None:
    workflow = replace(_chain(ran), seeds=False)
    execute(workflow, _chain_kwargs())
    del ran[:]

    execute(workflow, _chain_kwargs(source="alpha"))

    assert ran == [("deposits", "alpha"), ("currents", 200.0), ("waveforms", "standard")]
    assert _record(tmp_path / "toy")["options"]["source"] == "alpha"


def _marks(folder: Path) -> list[str]:
    return sorted(path.name for path in (folder / "batch").glob("*.done"))


def test_a_scanned_option_of_a_slice_with_new_events_runs_every_slice_in_each_point(
    started: list[Any], seeded: list[int], disk: dict[str, Any], ran: list[tuple[str, Any]], tmp_path: Path
) -> None:
    execute(_chain(ran), _chain_kwargs(scan=["voltage=200,300"]))

    assert ran == [
        ("deposits", "beta"),
        ("currents", 200),
        ("waveforms", "standard"),
        ("deposits", "beta"),
        ("currents", 300),
        ("waveforms", "standard"),
    ]
    assert "deposits_0.done" in _marks(tmp_path / "toy" / "voltage_300" / "seed_42")
    assert seeded[0] != seeded[3]  # the two points have deposits of their own


def test_another_name_of_a_point_leaves_the_seeds_of_its_jobs_as_they_are(
    started: list[Any], seeded: list[int], disk: dict[str, Any], ran: list[tuple[str, Any]], tmp_path: Path
) -> None:
    execute(_chain(ran), _chain_kwargs(scan=["voltage=200,300"]))
    named_by_voltage = list(seeded)
    shutil.rmtree(tmp_path / "toy")
    (tmp_path / "toy").mkdir()
    (tmp_path / "toy" / "config.json").write_text(
        json.dumps({"workflow": "toy", "device": "dev", "names": {"voltage": "bias"}})
    )
    del seeded[:]

    execute(_chain(ran), _chain_kwargs(scan=["bias=200,300"]))

    assert (tmp_path / "toy" / "bias_300" / "seed_42").is_dir()
    assert seeded == named_by_voltage


def test_points_that_differ_in_the_electronics_alone_draw_the_same_numbers_there(
    started: list[Any], seeded: list[int], disk: dict[str, Any], ran: list[tuple[str, Any]], tmp_path: Path
) -> None:
    execute(_chain(ran), _chain_kwargs(scan=["amplifier=standard,fast"]))

    assert [name for name, _ in ran] == ["deposits", "currents", "waveforms", "waveforms"]
    assert seeded[2] == seeded[3]  # nothing was measured anew: the noise is the same
    assert len(set(seeded[:3])) == 3  # each slice of a job draws from a seed of its own


def test_the_points_are_views_of_the_nodes_and_points_json_is_their_table(
    started: list[Any], seeded: list[int], disk: dict[str, Any], ran: list[tuple[str, Any]], tmp_path: Path
) -> None:
    execute(_chain(ran), _chain_kwargs(scan=["amplifier=standard,fast"]))
    experiment = tmp_path / "toy"

    table = json.loads((experiment / "points.json").read_text())
    assert sorted(table) == ["amplifier_fast", "amplifier_standard"]  # each by its value, the usual one too
    assert table["amplifier_fast"]["values"] == {"amplifier": "fast"}
    fast, unscanned = table["amplifier_fast"]["nodes"], table["amplifier_standard"]["nodes"]
    assert fast["deposits"] == unscanned["deposits"] and fast["currents"] == unscanned["currents"]
    assert fast["waveforms"] != unscanned["waveforms"]
    assert not os.path.lexists(experiment / "points" / "default")  # no point of a scan is the one without it
    for point, nodes_of_point in (("amplifier_fast", fast), ("amplifier_standard", unscanned)):
        for piece, listed in nodes_of_point.items():
            (node,) = listed  # one job
            link = experiment / "points" / point / piece / "0"
            assert link.resolve() == (experiment / "nodes" / piece / node).resolve()
            assert json.loads((link / "node.json").read_text())["state"] == "done"


def test_a_command_that_runs_points_of_its_own_leaves_the_table_of_the_experiment(
    started: list[Any], seeded: list[int], disk: dict[str, Any], ran: list[tuple[str, Any]], tmp_path: Path
) -> None:
    execute(_chain(ran), _chain_kwargs(scan=["amplifier=standard,fast"]))
    table = (tmp_path / "toy" / "points.json").read_text()

    execute(_chain(ran), _chain_kwargs(source="alpha"), register=False)

    assert (tmp_path / "toy" / "points.json").read_text() == table


def test_an_experiment_that_begins_to_scan_has_no_default_point_any_more(
    started: list[Any], seeded: list[int], disk: dict[str, Any], ran: list[tuple[str, Any]], tmp_path: Path
) -> None:
    points = tmp_path / "toy" / "points"
    execute(_chain(ran), _chain_kwargs())
    assert (points / "default").is_dir() and not (points / "default").is_symlink()

    execute(_chain(ran), _chain_kwargs(scan=["amplifier=standard,fast"]))
    assert sorted(path.name for path in points.iterdir()) == ["amplifier_fast", "amplifier_standard"]

    # The usual amplifier is no point of this scan: it has no view, though its
    # point still holds the deposits and the currents the two points read.
    execute(_chain(ran), _chain_kwargs(scan=["amplifier=fast,faster"]))
    assert sorted(path.name for path in points.iterdir()) == ["amplifier_fast", "amplifier_faster"]
    assert (points / "amplifier_faster" / "deposits" / "0" / "node.json").is_file()


def test_a_point_that_only_holds_slices_of_the_points_asked_has_no_view(
    started: list[Any], seeded: list[int], disk: dict[str, Any], ran: list[tuple[str, Any]], tmp_path: Path
) -> None:
    execute(_chain(ran), _chain_kwargs(scan=["amplifier=fast,faster"]))

    assert ("deposits", "beta") in ran  # run once, by the point of the usual amplifier
    points = tmp_path / "toy" / "points"
    assert sorted(path.name for path in points.iterdir()) == ["amplifier_fast", "amplifier_faster"]


def _counting(ran: list[tuple[str, Any]], monkeypatch: pytest.MonkeyPatch) -> Workflow:
    """The chain with two options that say how much, not what: the events of
    the deposits and the pictures of the currents. Registered, as a command is."""
    chain = _chain(ran)
    deposits = replace(chain.slices[0], keys=("source", "events"), counts=("events",))
    currents = replace(chain.slices[1], keys=("voltage", "draw"), counts=("draw",))
    workflow = replace(
        chain,
        slices=(deposits, currents, chain.slices[2]),
        keys=(*chain.keys, "events", "draw"),
        defaults={**chain.defaults, "events": 1, "draw": 0},
    )
    monkeypatch.setitem(workflow_module.WORKFLOWS, "toy", workflow)
    return workflow


def _counted(**given: Any) -> dict[str, Any]:
    return _chain_kwargs(**{"events": None, "draw": None, **given})


def test_runs_of_other_seeds_and_numbers_of_events_add_to_the_jobs_of_a_point(
    started: list[Any],
    seeded: list[int],
    disk: dict[str, Any],
    ran: list[tuple[str, Any]],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workflow = _counting(ran, monkeypatch)
    experiment = tmp_path / "toy"
    execute(workflow, _counted())
    # given on the command line, it is not in config.json; its jobs count all the same
    execute(workflow, _counted(events=40, seed=7))
    assert "events" not in json.loads((experiment / "config.json").read_text())["set"]

    ((name, values, jobs, others),) = workflow_module.jobs_of_points(experiment)

    assert (name, values, len(jobs), others) == ("default", {}, 2, [])
    assert workflow_module.batches(jobs) == "seed 42: 1 job, seed 7: 1 job"
    events = {
        json.loads((experiment / "nodes" / "deposits" / mine["deposits"] / "node.json").read_text())["inputs"][
            "settings"
        ]["events"]
        for _, mine in jobs
    }
    assert events == {1, 40}


def test_a_run_that_measured_something_else_is_not_among_the_jobs_of_the_point(
    started: list[Any],
    seeded: list[int],
    disk: dict[str, Any],
    ran: list[tuple[str, Any]],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workflow = _counting(ran, monkeypatch)
    experiment = tmp_path / "toy"
    execute(workflow, _counted())
    execute(workflow, _counted(seed=7))

    execute(workflow, _counted(source="alpha", seed=8))  # the point is of this source now
    ((_, _, jobs, others),) = workflow_module.jobs_of_points(experiment)
    assert len(jobs) == 1 and others == [(2, {"source": "beta"})]
    assert workflow_module.set_apart(others) == ["2 jobs measured something else and are not counted: source=beta"]

    execute(workflow, _counted(voltage=300.0, seed=9))  # and of this bias, with the usual source
    assert [len(jobs) for _, _, jobs, _ in workflow_module.jobs_of_points(experiment)] == [1]

    execute(workflow, _counted())
    assert [len(jobs) for _, _, jobs, _ in workflow_module.jobs_of_points(experiment)] == [2]

    disk["marker"] = "second"  # the files of the device and of the components changed
    execute(workflow, _counted(seed=10))
    assert [len(jobs) for _, _, jobs, _ in workflow_module.jobs_of_points(experiment)] == [1]


def test_points_that_read_the_same_deposits_through_other_electronics_each_have_their_job(
    started: list[Any],
    seeded: list[int],
    disk: dict[str, Any],
    ran: list[tuple[str, Any]],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workflow = _counting(ran, monkeypatch)
    execute(workflow, _counted(scan=["amplifier=standard,fast"]))

    points = workflow_module.jobs_of_points(tmp_path / "toy")

    assert [(name, len(jobs), others) for name, _, jobs, others in points] == [
        ("amplifier_fast", 1, []),
        ("amplifier_standard", 1, []),
    ]  # the job of the other point is counted there: it is not set apart here
    (_, fast), (_, standard) = points[0][2][0], points[1][2][0]
    assert fast["deposits"] == standard["deposits"] and fast["waveforms"] != standard["waveforms"]


def test_a_run_without_a_seed_is_told_by_its_time(
    started: list[Any],
    seeded: list[int],
    disk: dict[str, Any],
    ran: list[tuple[str, Any]],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workflow = _counting(ran, monkeypatch)
    monkeypatch.setattr(workflow_module.time, "strftime", lambda form: "2026_1122_190512")
    execute(workflow, _counted(seed=None))
    execute(workflow, _counted(seed=3, jobs=None))

    ((_, _, jobs, _),) = workflow_module.jobs_of_points(tmp_path / "toy")

    assert workflow_module.batches(jobs) == "seed 3: 1 job, the run of 2026_1122_190512, without --seed: 1 job"


def test_deposits_drawn_and_not_drawn_are_one_job_and_their_events_count_once(
    started: list[Any],
    seeded: list[int],
    disk: dict[str, Any],
    ran: list[tuple[str, Any]],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workflow = _counting(ran, monkeypatch)
    experiment = tmp_path / "toy"
    monkeypatch.setattr(workflow_module.time, "strftime", lambda form: "aside")
    execute(workflow, _counted())
    execute(workflow, _counted(draw=5))

    assert len(list((experiment / "nodes" / "currents").glob("*/node.json"))) == 2  # the same deposits, drifted twice
    assert [len(jobs) for _, _, jobs, _ in workflow_module.jobs_of_points(experiment)] == [1]


def test_a_job_counts_when_its_slices_have_their_nodes_or_one_of_them_ended_it(
    started: list[Any],
    seeded: list[int],
    disk: dict[str, Any],
    ran: list[tuple[str, Any]],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from raser.lifecycle import slices

    def nothing(options: dict[str, Any]) -> None:
        raise slices.Ended

    workflow = _counting(ran, monkeypatch)
    experiment = tmp_path / "toy"
    with pytest.raises(ValueError, match="no points.json"):
        workflow_module.jobs_of_points(experiment)
    failing = replace(workflow, slices=(workflow.slices[0], _chain(ran, fail="currents").slices[1], workflow.slices[2]))
    with pytest.raises(RuntimeError, match="currents"):
        execute(failing, _counted())
    assert [len(jobs) for _, _, jobs, _ in workflow_module.jobs_of_points(experiment)] == [0]  # no currents, no waveforms

    ending = replace(workflow, slices=(replace(workflow.slices[0], run=nothing), *workflow.slices[1:]))
    execute(ending, _counted(seed=7))
    ((_, _, jobs, _),) = workflow_module.jobs_of_points(experiment)
    assert [sorted(mine) for _, mine in jobs] == [["deposits"]]  # it recorded no event


def test_each_job_of_a_point_has_nodes_of_its_own(
    started: list[Any], seeded: list[int], disk: dict[str, Any], ran: list[tuple[str, Any]], tmp_path: Path
) -> None:
    execute(_chain(ran), _chain_kwargs(jobs=3))

    table = json.loads((tmp_path / "toy" / "points.json").read_text())["default"]["nodes"]

    assert {piece: len(set(listed)) for piece, listed in table.items()} == {
        "deposits": 3,
        "currents": 3,
        "waveforms": 3,
    }


def test_an_option_set_back_takes_the_nodes_written_before_and_runs_nothing(
    started: list[Any],
    seeded: list[int],
    disk: dict[str, Any],
    ran: list[tuple[str, Any]],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    times = iter(["first", "second"])  # the names of the runs kept aside
    monkeypatch.setattr(workflow_module.time, "strftime", lambda form: next(times))
    execute(_chain(ran), _chain_kwargs())
    execute(_chain(ran), _chain_kwargs(source="alpha"))
    del ran[:]

    execute(_chain(ran), _chain_kwargs(source="beta"))

    assert ran == []
    assert len(list((tmp_path / "toy" / "nodes" / "deposits").glob("*/node.json"))) == 2
    link = tmp_path / "toy" / "points" / "default" / "deposits" / "0"
    assert json.loads((link / "node.json").read_text())["inputs"]["settings"]["source"] == "beta"


def test_a_slice_that_failed_leaves_no_node_and_runs_again(
    started: list[Any], seeded: list[int], disk: dict[str, Any], ran: list[tuple[str, Any]], tmp_path: Path
) -> None:
    with pytest.raises(RuntimeError, match="currents"):
        execute(_chain(ran, fail="currents"), _chain_kwargs())

    half = [path for path in (tmp_path / "toy" / "nodes" / "currents").iterdir() if path.is_dir()]
    assert [path.name.endswith(".part") for path in half] == [True]
    del ran[:]
    execute(_chain(ran), _chain_kwargs())

    assert ran == [("currents", 200.0), ("waveforms", "standard")]
    whole = [path for path in (tmp_path / "toy" / "nodes" / "currents").iterdir() if path.is_dir()]
    assert [path.name.endswith(".part") for path in whole] == [False]


def test_a_slice_that_ends_the_job_leaves_a_node_that_says_so_and_none_after_it(
    started: list[Any], seeded: list[int], disk: dict[str, Any], ran: list[tuple[str, Any]], tmp_path: Path
) -> None:
    from raser.lifecycle import slices

    def nothing(options: dict[str, Any]) -> None:
        raise slices.Ended

    chain = _chain(ran)
    workflow = replace(chain, slices=(replace(chain.slices[0], run=nothing), *chain.slices[1:]))

    execute(workflow, _chain_kwargs())
    execute(workflow, _chain_kwargs())

    (node,) = (tmp_path / "toy" / "nodes" / "deposits").glob("*/node.json")
    assert json.loads(node.read_text())["state"] == "ended"
    assert ran == [] and not (tmp_path / "toy" / "nodes" / "currents").exists()
    assert (tmp_path / "toy" / "seed_42" / "batch" / "job_0.done").exists()


def test_with_same_seeds_the_slices_before_the_scanned_one_stay_in_the_unscanned_point(
    started: list[Any], seeded: list[int], disk: dict[str, Any], ran: list[tuple[str, Any]], tmp_path: Path
) -> None:
    execute(_chain(ran), _chain_kwargs(scan=["voltage=200,300"], same_seeds=True))

    assert ran == [
        ("deposits", "beta"),
        ("currents", 200),
        ("waveforms", "standard"),
        ("currents", 300),
        ("waveforms", "standard"),
    ]
    experiment = tmp_path / "toy"
    assert _marks(experiment / "seed_42") == ["deposits_0.done"]
    assert _marks(experiment / "voltage_200" / "seed_42") == [
        "currents_0.done",
        "job_0.done",
        "waveforms_0.done",
    ]
    assert _marks(experiment / "voltage_300" / "seed_42") == [
        "currents_0.done",
        "job_0.done",
        "waveforms_0.done",
    ]


def test_the_unscanned_point_runs_only_the_slices_other_points_have_in_it(
    started: list[Any], seeded: list[int], disk: dict[str, Any], ran: list[tuple[str, Any]], tmp_path: Path
) -> None:
    execute(_chain(ran), _chain_kwargs(scan=["amplifier=fast,slow"]))

    assert ran == [
        ("deposits", "beta"),
        ("currents", 200.0),
        ("waveforms", "fast"),
        ("waveforms", "slow"),
    ]
    experiment = tmp_path / "toy"
    assert _marks(experiment / "seed_42") == ["currents_0.done", "deposits_0.done"]
    assert _marks(experiment / "amplifier_slow" / "seed_42") == ["job_0.done", "waveforms_0.done"]
    points = workflow_module.finished(_chain(ran), _chain_kwargs(), experiment)
    assert [(name, len(done)) for name, _, done in points] == [("amplifier_fast", 1), ("amplifier_slow", 1)]


def test_a_slice_is_told_the_node_of_every_slice_and_writes_into_its_own(
    started: list[Any], seeded: list[int], disk: dict[str, Any], tmp_path: Path
) -> None:
    told: list[tuple[str, Any, dict[str, str], int]] = []

    def piece(name: str, key: str) -> Slice:
        def run(options: dict[str, Any]) -> None:
            told.append((name, options[key], dict(options["_node_paths"]), options["seed"]))

        return Slice(name, run, keys=(key,))

    workflow = Workflow(
        name="toy",
        slices=(piece("deposits", "source"), piece("currents", "voltage")),
        keys=("source", "voltage"),
        defaults={"source": "beta"},
        in_file={"voltage": "device.bias.voltage"},
    )
    execute(workflow, _chain_kwargs(scan=["voltage=300,400"], same_seeds=True))
    alone = len(told)
    execute(workflow, _chain_kwargs(scan=["voltage=300"], same_seeds=True))

    experiment = tmp_path / "toy"
    assert [(name, value) for name, value, _, _ in told[:alone]] == [
        ("deposits", "beta"),
        ("currents", 300),
        ("currents", 400),
    ]
    at_300, at_400 = told[1][2], told[2][2]
    # The deposits both points read are one node, whole; each writes currents of its own.
    assert Path(at_300["deposits"]).parent == experiment / "nodes" / "deposits"
    assert (Path(at_300["deposits"]) / "node.json").is_file()
    assert at_400["deposits"] == at_300["deposits"]
    assert Path(at_300["currents"]).parent == experiment / "nodes" / "currents"
    assert at_300["currents"].endswith(".part") and at_400["currents"].endswith(".part")
    assert at_300["currents"] != at_400["currents"]
    assert told[alone:] == []  # the second command finds everything done


def test_a_point_whose_earlier_slice_failed_elsewhere_is_not_started_and_is_reported(
    started: list[Any], seeded: list[int], disk: dict[str, Any], ran: list[tuple[str, Any]]
) -> None:
    with pytest.raises(SystemExit, match="wait for deposits"):
        execute(_chain(ran, fail="deposits"), _chain_kwargs(scan=["voltage=300,400"], same_seeds=True))

    assert ran == []


def _seeds_of_slices(name: str, scan: list[str], same_seeds: bool) -> dict[tuple[str, Any], int]:
    """(slice, the value of its own option) -> its seed, for one command of the workflow `name`."""
    told: dict[tuple[str, Any], int] = {}

    def piece(name: str, key: str) -> Slice:
        return Slice(name, lambda options: told.update({(name, options[key]): options["seed"]}), keys=(key,))

    workflow = Workflow(
        name=name,
        slices=(piece("deposits", "source"), piece("currents", "voltage")),
        keys=("source", "voltage"),
        defaults={"source": "beta"},
        in_file={"voltage": "device.bias.voltage"},
    )
    execute(workflow, _chain_kwargs(scan=scan, same_seeds=same_seeds))
    return told


def test_each_slice_draws_numbers_of_its_own_and_same_seeds_gives_the_points_the_same(
    started: list[Any], seeded: list[int], disk: dict[str, Any]
) -> None:
    unscanned = _seeds_of_slices("one", [], same_seeds=False)
    scanned = _seeds_of_slices("other", ["voltage=300,400"], same_seeds=False)
    shared = _seeds_of_slices("third", ["voltage=300,400"], same_seeds=True)
    alone = _seeds_of_slices("fourth", [], same_seeds=True)

    assert unscanned["deposits", "beta"] != unscanned["currents", 200.0]
    assert scanned["currents", 300] != scanned["currents", 400]
    assert shared["currents", 300] == shared["currents", 400]
    assert shared["deposits", "beta"] == alone["deposits", "beta"]


def test_a_second_command_starts_no_job_in_a_point_that_only_holds_slices_of_others(
    started: list[Any],
    seeded: list[int],
    disk: dict[str, Any],
    ran: list[tuple[str, Any]],
    capsys: pytest.CaptureFixture[str],
) -> None:
    execute(_chain(ran), _chain_kwargs(scan=["amplifier=fast,slow"]))
    capsys.readouterr()

    execute(_chain(ran), _chain_kwargs(scan=["amplifier=fast,slow"]))

    lines = capsys.readouterr().out.splitlines()
    assert lines[0].endswith("toy/seed_42: jobs []")
    assert [line.split() for line in lines[1:3]] == [["deposits", "reused"], ["currents", "reused"]]
    assert lines[3].endswith("amplifier_fast/seed_42: jobs []")


def test_a_slice_does_not_start_while_one_before_it_is_not_done_where_it_is_held(tmp_path: Path) -> None:
    from raser.lifecycle import slices

    ran: list[str] = []
    chain = (Slice("deposits", lambda options: ran.append("deposits")), Slice("currents", lambda options: ran.append("currents")))
    folders = {"deposits": tmp_path / "upstream", "currents": tmp_path / "here"}
    for folder in folders.values():
        (folder / "batch").mkdir(parents=True)

    with pytest.raises(RuntimeError, match="currents of job 0 needs deposits"):
        slices.run(chain, folders, 0, {}, ["currents"], lambda piece: None)
    assert ran == []

    slices.mark(folders["deposits"], 0, "deposits").touch()
    assert slices.run(chain, folders, 0, {}, ["currents"], lambda piece: None)
    assert ran == ["currents"]


def test_a_slice_that_ends_the_job_leaves_it_done_and_the_later_slices_unrun_in_every_point(tmp_path: Path) -> None:
    from raser.lifecycle import slices

    ran: list[str] = []

    def no_event(options) -> None:
        ran.append("deposits")
        raise slices.Ended

    chain = (
        Slice("deposits", no_event),
        Slice("currents", lambda options: ran.append("currents")),
        Slice("waveforms", lambda options: ran.append("waveforms")),
    )
    here = {name: tmp_path / "here" for name in ("deposits", "currents", "waveforms")}
    other = {**here, "waveforms": tmp_path / "other"}  # a point that only has its own waveforms
    for folder in (tmp_path / "here", tmp_path / "other"):
        (folder / "batch").mkdir(parents=True)

    assert slices.run(chain, here, 0, {}, ["deposits", "currents", "waveforms"], lambda piece: None)
    assert slices.run(chain, other, 0, {}, ["waveforms"], lambda piece: None)
    assert ran == ["deposits"]

    # a job that did record events is not held back by the one that ended
    assert slices.run(chain[1:], here, 1, {}, ["currents", "waveforms"], lambda piece: None)
    assert ran == ["deposits", "currents", "waveforms"]


def test_a_mark_cut_short_by_a_kill_leaves_the_slice_to_run_again_and_does_not_lose_its_end(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from raser.lifecycle import slices

    ran: list[str] = []

    def no_event(options) -> None:
        ran.append("deposits")
        raise slices.Ended

    chain = (Slice("deposits", no_event), Slice("currents", lambda options: ran.append("currents")))
    folders = {name: tmp_path for name in ("deposits", "currents")}
    (tmp_path / "batch").mkdir()

    def killed(self, text, *args, **kwargs):
        open(self, "w").close()  # the file is opened, then the process is killed
        raise KeyboardInterrupt

    with monkeypatch.context() as patched:
        patched.setattr(Path, "write_text", killed)
        with pytest.raises(KeyboardInterrupt):
            slices.run(chain, folders, 0, {}, ["deposits", "currents"], lambda piece: None)

    assert slices.run(chain, folders, 0, {}, ["deposits", "currents"], lambda piece: None)
    assert ran == ["deposits", "deposits"]


def test_a_job_killed_after_its_last_slice_mark_is_done_at_the_next_command(
    started: list[Any], seeded: list[int], disk: dict[str, Any], ran: list[tuple[str, Any]], tmp_path: Path
) -> None:
    execute(_chain(ran), _chain_kwargs())
    whole = tmp_path / "toy" / "seed_42" / "batch" / "job_0.done"
    whole.unlink()
    ran.clear()

    execute(_chain(ran), _chain_kwargs())

    assert ran == []
    assert whole.exists()


def test_a_file_read_by_a_function_of_the_app_is_judged_and_handed_to_the_job_as_it_was_read(
    started: list[Any], seeded: list[int], disk: dict[str, Any], ran: list[tuple[str, Any]]
) -> None:
    circuit = {"R1": {"ohm": 470.0}}  # what the SPICE file of the amplifier holds
    handed: list[Any] = []

    def waveforms(options: dict[str, Any]) -> None:
        ran.append(("waveforms", options["amplifier"]))
        handed.append(options["_files"]["afe"])

    chain = _chain(ran)
    last = replace(chain.slices[2], run=waveforms)
    workflow = replace(
        chain, slices=(*chain.slices[:2], last), readers={"afe": lambda name: {"name": name, **circuit}}
    )

    execute(workflow, _chain_kwargs())
    execute(workflow, _chain_kwargs())
    circuit["R1"] = {"ohm": 499.0}  # the file is edited
    execute(workflow, _chain_kwargs())

    assert ran == [("deposits", "beta"), ("currents", 200.0), ("waveforms", "standard"), ("waveforms", "standard")]
    assert handed == [{"name": "standard", "R1": {"ohm": 470.0}}, {"name": "standard", "R1": {"ohm": 499.0}}]


def test_what_a_slice_returns_is_kept_with_its_mark_and_does_not_end_the_job(tmp_path: Path) -> None:
    from raser.lifecycle import slices

    ran: list[str] = []
    field = {"field": {"folder": "work/dev/field", "commit": "abc"}}
    chain = (
        Slice("currents", lambda options: field),
        Slice("waveforms", lambda options: ran.append("waveforms")),
    )
    folders = {name: tmp_path for name in ("currents", "waveforms")}
    (tmp_path / "batch").mkdir()

    assert slices.run(chain, folders, 0, {}, ["currents", "waveforms"], lambda piece: None)

    assert slices.notes(tmp_path, 0, "currents") == field
    assert slices.notes(tmp_path, 0, "waveforms") == {}
    assert ran == ["waveforms"]


def test_a_folder_or_a_job_that_another_process_holds_is_not_run_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("RASER_PROJECT_PATH", str(tmp_path))
    monkeypatch.setattr(workflow_module, "_commit", lambda: "abc")
    ran: list[int] = []
    toy = Workflow(name="toy", job=lambda options: ran.append(1), device=False, seeds=False)
    other = workflow_module._lock(workflow_module._folder_lock(tmp_path / "toy"), "toy")  # another command

    with pytest.raises(workflow_module.Running):
        execute(toy, _plain())
    assert not (tmp_path / "toy" / "run.json").exists()

    other.close()
    execute(toy, _plain())
    job = workflow_module._lock(tmp_path / "toy" / "batch" / "job_0.lock", "job 0")  # the job runs elsewhere
    with pytest.raises(workflow_module.Running):
        workflow_module._run_job(toy, {"job_dir": str(tmp_path / "toy")})
    job.close()
    assert ran == [1]


def test_a_command_that_finds_a_folder_held_leaves_the_config_as_it_was(
    started: list[Any], tmp_path: Path
) -> None:
    execute(GAIN, _kwargs(gain=None, width=None, jobs=2))
    config = (tmp_path / "toy" / "config.json").read_text()
    other = workflow_module._lock(workflow_module._folder_lock(tmp_path / "toy" / "seed_42"), "seed_42")

    with pytest.raises(workflow_module.Running):
        execute(GAIN, _kwargs(gain=None, width=None, jobs=2, set=["gain=7"]))
    other.close()

    assert (tmp_path / "toy" / "config.json").read_text() == config


def test_while_one_command_holds_the_config_another_waits_for_it_and_neither_loses_its_scan(
    started: list[Any], tmp_path: Path
) -> None:
    execute(GAIN, _kwargs(gain=None, width=None, jobs=2))
    other = workflow_module._lock(tmp_path / ".toy.config.lock", "toy")  # another command reads the config

    with pytest.raises(workflow_module.Running, match="toy"):
        execute(GAIN, _kwargs(gain=None, width=None, jobs=2, seed=43, scan=["gain=7,8"]))
    other.close()
    assert "gain" not in json.loads((tmp_path / "toy" / "config.json").read_text())["scan"]

    execute(GAIN, _kwargs(gain=None, width=None, jobs=2, seed=43, scan=["gain=7,8"]))
    execute(GAIN, _kwargs(gain=None, width=None, jobs=2, seed=44, scan=["width=2.0"]))
    assert json.loads((tmp_path / "toy" / "config.json").read_text())["scan"] == {"gain": [7, 8], "width": [2.0]}


def test_a_file_system_that_cannot_lock_warns_and_lets_the_run_go_on(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def refuse(handle, how):
        raise OSError(errno.ENOLCK, "No locks available")

    monkeypatch.setattr(workflow_module.fcntl, "flock", refuse)

    assert workflow_module._lock(tmp_path / "x.lock", "x") is None
    assert "cannot be locked here (No locks available)" in capsys.readouterr().out


def test_more_jobs_asked_of_a_seed_folder_add_to_it_and_do_not_make_it_out_of_date(
    started: list[Any], tmp_path: Path
) -> None:
    execute(TOY, _kwargs(jobs=3))
    execute(TOY, _kwargs(jobs=5))

    assert [jobs for _, _, jobs, _ in started] == [[0, 1, 2], [3, 4]]
    assert json.loads((tmp_path / "toy" / "seed_42" / "run.json").read_text())["jobs"] == 5
    (tmp_path / "toy" / "seed_42" / "batch" / "job_1.done").unlink()  # a job to redo with fewer asked
    execute(TOY, _kwargs(jobs=3))
    assert json.loads((tmp_path / "toy" / "seed_42" / "run.json").read_text())["jobs"] == 5


def test_a_set_value_is_one_value_at_an_address_and_a_new_experiment_keeps_it(
    started: list[Any], tmp_path: Path
) -> None:
    execute(GAIN, _kwargs(gain=None, width=None, set=["width=2.5"], jobs=2))

    config = json.loads((tmp_path / "toy" / "config.json").read_text())
    assert config["set"] == {"width": 2.5}
    assert _options(tmp_path / "toy" / "seed_42")["width"] == 2.5


def test_a_set_value_by_short_name_replaces_the_one_the_config_had_and_runs_again(
    started: list[Any], tmp_path: Path
) -> None:
    experiment = tmp_path / "toy"
    experiment.mkdir()
    config = {"workflow": "toy", "set": {"gain": 5}, "scan": {}, "names": {"gain": "g"}}
    (experiment / "config.json").write_text(json.dumps(config))
    execute(GAIN, _kwargs(gain=None, width=None, jobs=2))

    execute(GAIN, _kwargs(gain=None, width=None, set=["g=7"], jobs=2))

    assert json.loads((experiment / "config.json").read_text())["set"] == {"gain": 7}
    assert _options(experiment / "seed_42")["gain"] == 7
    assert len(_kept(experiment)) == 1  # the run with gain 5 is kept aside


def test_one_address_given_to_set_and_to_scan_at_once_is_refused(started: list[Any]) -> None:
    with pytest.raises(ValueError, match="gain: given to --set and to --scan at once"):
        execute(GAIN, _kwargs(gain=None, width=None, set=["gain=7"], scan=["gain=5,9"], jobs=2))


def test_a_point_run_unregistered_leaves_the_config_and_runs_none_of_its_scans(
    started: list[Any], tmp_path: Path
) -> None:
    experiment = tmp_path / "toy"
    experiment.mkdir()
    config = {"workflow": "toy", "set": {}, "scan": {"width": [1.0, 2.0]}}
    (experiment / "config.json").write_text(json.dumps(config))

    execute(GAIN, _kwargs(gain=None, width=None, scan=["gain=7"], jobs=2), register=False)

    assert json.loads((experiment / "config.json").read_text()) == config
    assert _folders(started, experiment) == ["gain_7/seed_42"]


def test_a_new_experiment_made_for_an_unregistered_point_keeps_no_scan(
    started: list[Any], tmp_path: Path
) -> None:
    execute(GAIN, _kwargs(gain=None, width=None, scan=["gain=7"], jobs=2), register=False)

    assert json.loads((tmp_path / "toy" / "config.json").read_text())["scan"] == {}


def test_a_job_run_in_this_process_leaves_a_log_with_what_it_printed_and_why_it_failed(
    started: list[Any], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    def job(options: dict[str, Any]) -> None:
        print("collected 3 points")
        raise RuntimeError("no event selected")

    with pytest.raises(RuntimeError):
        execute(Workflow(name="toy", job=job, device=False), _kwargs())

    log = (tmp_path / "toy" / "seed_42" / "batch" / "job_0.log").read_text()
    assert "collected 3 points" in capsys.readouterr().out and "collected 3 points" in log
    assert log.rstrip().endswith("RuntimeError: no event selected")


def test_a_job_of_slices_run_in_this_process_ends_its_log_with_the_slices_it_ran(
    started: list[Any], seeded: list[int], disk: dict[str, Any], ran: list[tuple[str, Any]], tmp_path: Path
) -> None:
    execute(_chain(ran), _chain_kwargs(until="deposits"))

    log = (tmp_path / "toy" / "seed_42" / "batch" / "job_0.log").read_text()
    assert f"{workflow_module.JOB_ENDED}: deposits" in log


@pytest.mark.parametrize(
    "given",
    [
        {"scan": ["gain=5*(step(x)-1)"]},
        {"set": ["gain=5*(step(x)-1)"]},
    ],
)
def test_a_value_that_cannot_name_a_folder_is_refused(started: list[Any], given: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="holds more than letters, digits and"):
        execute(GAIN, _kwargs(gain=None, width=None, jobs=2, **given))
    assert started == []


def test_two_values_that_would_name_one_folder_are_refused(started: list[Any]) -> None:
    with pytest.raises(ValueError, match="'beam/muon' and 'other/muon' would both be the folder 'muon'"):
        execute(GAIN, _kwargs(gain=None, width=None, scan=["gain=beam/muon,other/muon"], jobs=2))


def _branches(ran: list[tuple[str, Any]]) -> Workflow:
    """A first slice that nothing here changes; two slices that read no other
    and share the option x; between them one of its own option y that reads
    none; last one that reads the two of x."""

    def piece(name: str, keys: tuple, needs: tuple) -> Slice:
        return Slice(name, lambda options: ran.append((name, options.get("x"))), keys=keys, needs=needs)

    return Workflow(
        name="toy",
        slices=(
            piece("r", ("z",), ()),
            piece("a", ("x",), ()),
            piece("d", ("y",), ()),
            piece("b", ("x",), ()),
            piece("c", (), ("a", "b")),
        ),
        keys=("x", "y", "z"),
        defaults={"x": 1, "y": 1, "z": 1},
        device=False,
    )


def test_an_option_two_slices_read_runs_both_again_and_what_reads_them_but_not_the_rest(
    started: list[Any], seeded: list[int], ran: list[tuple[str, Any]]
) -> None:
    execute(_branches(ran), _kwargs())
    ran.clear()

    execute(_branches(ran), _kwargs(x=2))

    assert [name for name, _ in ran] == ["a", "b", "c"]


def test_an_option_of_a_slice_nothing_reads_runs_that_slice_alone_again(
    started: list[Any], seeded: list[int], ran: list[tuple[str, Any]]
) -> None:
    execute(_branches(ran), _kwargs())
    ran.clear()

    execute(_branches(ran), _kwargs(y=2))

    assert [name for name, _ in ran] == ["d"]


def test_with_same_seeds_a_point_whose_two_roots_are_held_by_two_others_runs_each_root_once(
    started: list[Any], seeded: list[int], tmp_path: Path
) -> None:
    ran: list[tuple[str, Any]] = []

    def piece(name: str, key: str) -> Slice:
        return Slice(name, lambda options: ran.append((name, options[key])), keys=(key,), needs=())

    workflow = Workflow(
        name="toy", slices=(piece("a", "x"), piece("b", "y")), keys=("x", "y"), defaults={"x": 1, "y": 1}, device=False
    )

    execute(workflow, _kwargs(scan=["x=2", "y=2"], same_seeds=True))

    assert sorted(ran) == [("a", 2), ("b", 2)]
    assert (tmp_path / "toy" / "x_2" / "seed_42" / "run.json").exists()
    assert (tmp_path / "toy" / "y_2" / "seed_42" / "run.json").exists()


def test_an_option_of_one_of_two_roots_runs_that_root_again_in_place_and_not_the_other(
    started: list[Any], seeded: list[int], tmp_path: Path
) -> None:
    ran: list[tuple[str, Any]] = []

    def piece(name: str, key: str) -> Slice:
        return Slice(name, lambda options: ran.append((name, options[key])), keys=(key,), needs=())

    workflow = Workflow(
        name="toy", slices=(piece("a", "x"), piece("b", "y")), keys=("x", "y"), defaults={"x": 1, "y": 1}, device=False
    )
    execute(workflow, _kwargs())
    ran.clear()

    execute(workflow, _kwargs(x=2))

    assert ran == [("a", 2)]
    assert _kept(tmp_path / "toy") == []


# a and b: one of them is given, a by default
EITHER = Workflow(
    name="toy", job=lambda options: None, keys=("a", "b"), defaults={"a": 1}, device=False, exclusive=(("a", "b"),)
)


def test_a_key_of_a_group_given_leaves_out_the_default_of_the_other(started: list[Any], tmp_path: Path) -> None:
    execute(EITHER, _kwargs(b=5))

    options = _options(tmp_path / "toy" / "seed_42")
    assert options["b"] == 5 and "a" not in options


def test_the_command_line_decides_a_group_over_the_set_of_the_config(started: list[Any], tmp_path: Path) -> None:
    experiment = tmp_path / "toy"
    experiment.mkdir()
    (experiment / "config.json").write_text(json.dumps({"workflow": "toy", "set": {"b": 5}, "scan": {}}))

    execute(EITHER, _kwargs())
    assert "a" not in _options(experiment / "seed_42")  # the set's b over the default a

    execute(EITHER, _kwargs(a=2, seed=43))
    options = _options(experiment / "seed_43")
    assert options["a"] == 2 and "b" not in options


def test_a_key_of_a_group_scanned_leaves_out_the_default_of_the_other_in_every_point(
    started: list[Any], tmp_path: Path
) -> None:
    execute(EITHER, _kwargs(scan=["b=2,3"]))

    points = [_options(tmp_path / "toy" / name / "seed_42") for name in ("b_2", "b_3")]
    assert [(options["b"], "a" in options) for options in points] == [(2, False), (3, False)]


def test_a_key_of_a_group_set_replaces_the_other_in_the_config_and_the_next_command_runs(
    started: list[Any], tmp_path: Path
) -> None:
    experiment = tmp_path / "toy"
    experiment.mkdir()
    (experiment / "config.json").write_text(json.dumps({"workflow": "toy", "set": {"a": 1}, "scan": {}}))

    execute(EITHER, _kwargs(set=["b=2"]))
    execute(EITHER, _kwargs(seed=43))

    assert json.loads((experiment / "config.json").read_text())["set"] == {"b": 2}
    options = _options(experiment / "seed_43")
    assert options["b"] == 2 and "a" not in options


def test_a_value_set_for_a_scanned_option_ends_its_scan_for_the_next_commands(
    started: list[Any], tmp_path: Path
) -> None:
    experiment = tmp_path / "toy"
    experiment.mkdir()
    (experiment / "config.json").write_text(json.dumps({"workflow": "toy", "set": {}, "scan": {"gain": [5, 7]}}))

    execute(GAIN, _kwargs(gain=None, width=None, set=["gain=6"], jobs=2))
    started.clear()
    execute(GAIN, _kwargs(gain=None, width=None, jobs=2, seed=43))

    assert _folders(started, experiment) == ["seed_43"]
    assert _options(experiment / "seed_43")["gain"] == 6


def test_two_keys_of_a_group_in_one_layer_are_refused(started: list[Any]) -> None:
    with pytest.raises(ValueError, match="a and b are given at once in the command line"):
        execute(EITHER, _kwargs(a=2, b=5))
    with pytest.raises(ValueError, match="a and b are given at once in the defaults of toy"):
        Workflow(name="toy", keys=("a", "b"), defaults={"a": 1, "b": 2}, exclusive=(("a", "b"),))


def test_a_setting_of_the_command_line_that_changed_makes_the_run_out_of_date_whatever_the_workflow_judges(
    started: list[Any], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ran: list[bool] = []
    solver = Workflow(
        name="toy",
        job=lambda options: ran.append(options["umf"]),
        device=False,
        seeds=False,
        outdated=lambda old, record: None,  # the field judges only its device and flux
        settings=lambda kwargs: {"umf": bool(kwargs.get("umf"))},
    )
    execute(solver, _plain(umf=False))
    execute(solver, _plain(umf=False))
    assert "replaced" not in capsys.readouterr().out  # the same settings

    execute(solver, _plain(umf=True))

    assert ran[-1] is True
    assert "replaced: other settings of the command line" in capsys.readouterr().out
    assert _record(tmp_path / "toy")["settings"] == {"umf": True}

    old = _record(tmp_path / "toy")
    # written before the settings were recorded: made with the default ones
    for asked, replaced in ((False, False), (True, True)):
        old = {key: value for key, value in old.items() if key != "settings"}
        (tmp_path / "toy" / "run.json").write_text(json.dumps(old))
        execute(solver, _plain(umf=asked))
        assert ("replaced: other settings of the command line" in capsys.readouterr().out) is replaced


def _in_sections(seen: list[tuple[str, Any, Any]]) -> Workflow:
    """A chain written in sections: the deposits and the currents each have
    plots, the readout an amplifier whose file is the slot readout.amplifier."""

    def piece(name: str, keys: tuple, **more: Any) -> Slice:
        def run(options: dict[str, Any]) -> None:
            seen.append((name, options["plots"], options["amplifier"]))

        return Slice(name, run, keys=keys, **more)

    return Workflow(
        name="toy",
        slices=(
            piece("deposit", ("deposit.plots", "deposit.source", "deposit.limit")),
            piece("current", ("current.plots",)),
            piece("readout", ("readout.amplifier",), kinds=("readout.amplifier",), new_events=False),
        ),
        keys=("deposit.source", "deposit.plots", "deposit.limit", "current.plots", "readout.amplifier", "analysis.cuts"),
        # deposit.limit is set by nothing: null in config.json
        defaults={
            "deposit.source": "beta",
            "deposit.plots": 7,
            "current.plots": 3,
            "readout.amplifier": "standard",
            "analysis.cuts": [1, 2],  # a list that is one value: the analysis is not scanned
        },
        components={"afe": "readout.amplifier"},
        sections=("deposit", "current", "readout", "analysis"),
        scanned=("deposit", "current", "readout"),
        slots={"readout.amplifier": "afe"},
    )


def _config(tmp_path: Path) -> dict[str, Any]:
    return json.loads((tmp_path / "toy" / "config.json").read_text())


def test_a_config_in_sections_is_written_whole_and_each_stage_reads_its_own_section(
    started: list[Any], seeded: list[int], disk: dict[str, Any], tmp_path: Path
) -> None:
    seen: list[tuple[str, Any, Any]] = []

    execute(_in_sections(seen), _chain_kwargs())

    assert _config(tmp_path) == {
        "workflow": "toy",
        "device": "dev",
        "deposit": {"source": "beta", "plots": 7, "limit": None},
        "current": {"plots": 3},
        "readout": {"amplifier": "standard"},
        "analysis": {"cuts": [1, 2]},
        "names": {},
        "same_seeds": False,
    }
    # plots is 7 to the deposits and 3 to the currents; the readout, which has none, sees one of them
    assert seen[:2] == [("deposit", 7, "standard"), ("current", 3, "standard")]

    del seen[:]
    execute(_in_sections(seen), _chain_kwargs())  # the same command reads the config it wrote: nothing runs again
    assert seen == []


def test_set_and_scan_write_their_sections_and_stay_for_the_commands_after(
    started: list[Any], seeded: list[int], disk: dict[str, Any], tmp_path: Path
) -> None:
    seen: list[tuple[str, Any, Any]] = []
    workflow = _in_sections(seen)
    execute(workflow, _chain_kwargs())

    execute(workflow, _chain_kwargs(set=["current.plots=0"], scan=["readout.amplifier=standard,fast"]))
    del seen[:]
    execute(workflow, _chain_kwargs(seed=7))  # no option: what the config holds

    config = _config(tmp_path)
    assert config["current"] == {"plots": 0} and config["deposit"]["plots"] == 7
    assert config["readout"] == {"amplifier": ["standard", "fast"]}  # a list where what is measured is set: a scan
    assert "scan" not in config
    assert sorted(seen) == [("current", 0, "standard"), ("deposit", 7, "standard"), ("readout", 0, "fast"), ("readout", 0, "standard")]
    assert (tmp_path / "toy" / "points" / "amplifier_fast").is_dir()  # named by the key without its section

    execute(workflow, _chain_kwargs(set=["readout.amplifier=fast"]))  # a set of the key ends its scan
    assert _config(tmp_path)["readout"] == {"amplifier": "fast"}
    assert sorted(path.name for path in (tmp_path / "toy" / "points").iterdir()) == ["default"]


def test_a_setting_of_the_analysis_is_not_scanned_and_its_list_is_one_value(
    started: list[Any], seeded: list[int], disk: dict[str, Any], tmp_path: Path
) -> None:
    seen: list[tuple[str, Any, Any]] = []
    workflow = _in_sections(seen)

    with pytest.raises(ValueError, match="analysis.cuts is not scanned.*Scanned are the settings of deposit, current, readout"):
        execute(workflow, _chain_kwargs(scan=["analysis.cuts=1,2"]))
    assert seen == []

    with pytest.raises(ValueError, match="current.plots: a list of values is a scan; give it to --scan as current.plots=0,5"):
        execute(workflow, _chain_kwargs(set=["current.plots=[0, 5]"]))
    execute(workflow, _chain_kwargs(set=["analysis.cuts=[3, 4, 5]"]))

    assert _config(tmp_path)["analysis"] == {"cuts": [3, 4, 5]}
    assert sorted(path.name for path in (tmp_path / "toy" / "points").iterdir()) == ["default"]  # one run


def test_a_key_set_inside_a_component_stays_in_the_object_of_its_slot_until_the_slot_takes_another(
    started: list[Any], seeded: list[int], disk: dict[str, Any], tmp_path: Path
) -> None:
    seen: list[tuple[str, Any, Any]] = []
    workflow = _in_sections(seen)
    execute(workflow, _chain_kwargs(set=["readout.amplifier.marker=second"]))
    assert _config(tmp_path)["readout"] == {"amplifier": {"name": "standard", "marker": "second"}}

    execute(workflow, _chain_kwargs(seed=7))  # no option: the key is in the config
    record = json.loads((tmp_path / "toy" / "seed_7" / "run.json").read_text())
    assert record["files"]["afe"]["marker"] == "second" and record["options"]["readout.amplifier"] == "standard"

    execute(workflow, _chain_kwargs(scan=["readout.amplifier.marker=second,third"], seed=8))
    assert _config(tmp_path)["readout"] == {"amplifier": {"name": "standard", "marker": ["second", "third"]}}

    execute(workflow, _chain_kwargs(set=["readout.amplifier=fast"], seed=9))  # another file: its keys are its own
    assert _config(tmp_path)["readout"] == {"amplifier": "fast"}


def test_the_run_that_puts_another_component_in_a_slot_reads_no_key_set_inside_the_one_before(
    started: list[Any], seeded: list[int], disk: dict[str, Any], tmp_path: Path
) -> None:
    seen: list[tuple[str, Any, Any]] = []
    workflow = _in_sections(seen)
    execute(workflow, _chain_kwargs(set=["readout.amplifier.marker=second"]))

    execute(workflow, _chain_kwargs(set=["readout.amplifier=fast"], seed=7))

    record = json.loads((tmp_path / "toy" / "seed_7" / "run.json").read_text())
    assert record["files"]["afe"] == {"kind": "afe", "selector": "fast", "marker": "first"}
    assert _config(tmp_path)["readout"] == {"amplifier": "fast"}


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda config: config["current"].update(plot=1), "no current.plot; the settings of current are plots"),
        (lambda config: config.update(set={"deposit.plots": 1}), "no set in a config.json"),
        (lambda config: config.update(readout="fast"), "readout is a section"),
    ],
)
def test_a_config_that_holds_what_no_stage_knows_is_refused(
    started: list[Any], seeded: list[int], disk: dict[str, Any], tmp_path: Path, change: Any, message: str
) -> None:
    seen: list[tuple[str, Any, Any]] = []
    workflow = _in_sections(seen)
    execute(workflow, _chain_kwargs())
    config = _config(tmp_path)
    change(config)
    (tmp_path / "toy" / "config.json").write_text(json.dumps(config))
    del seen[:]

    with pytest.raises(ValueError, match=message):
        execute(workflow, _chain_kwargs(seed=7))

    assert seen == []


def test_a_setting_that_config_json_does_not_write_is_null(
    started: list[Any], seeded: list[int], disk: dict[str, Any], tmp_path: Path
) -> None:
    seen: list[tuple[str, Any, Any]] = []
    workflow = _in_sections(seen)
    execute(workflow, _chain_kwargs())
    config = _config(tmp_path)
    del config["current"]["plots"]
    (tmp_path / "toy" / "config.json").write_text(json.dumps(config))
    del seen[:]

    execute(workflow, _chain_kwargs(seed=7))

    assert ("current", None, "standard") in seen


def test_a_key_inside_a_component_is_given_through_its_slot_and_no_other_address_is_a_setting(
    started: list[Any], seeded: list[int], disk: dict[str, Any], tmp_path: Path
) -> None:
    seen: list[tuple[str, Any, Any]] = []
    workflow = _in_sections(seen)

    execute(workflow, _chain_kwargs(set=["readout.amplifier.marker=second"]))

    record = json.loads((tmp_path / "toy" / "seed_42" / "run.json").read_text())
    assert record["files"]["afe"]["marker"] == "second"
    with pytest.raises(ValueError, match="deposit.event: no such setting"):
        execute(workflow, _chain_kwargs(set=["deposit.event=5"], seed=7))
    with pytest.raises(ValueError, match="afe.marker: no such setting"):
        execute(workflow, _chain_kwargs(set=["afe.marker=third"], seed=8))
    with pytest.raises(ValueError, match="plots: no such setting"):  # a key without its section
        execute(workflow, _chain_kwargs(scan=["plots=0,5"], seed=9))



# Deliberate change: the check dropped, so that the loader is given None and ends in a TypeError.
def test_a_component_that_no_setting_names_is_told_by_its_address() -> None:
    workflow = Workflow(name="toy", job=print, keys=("deposit.source",), components={"source": "deposit.source"}, device=False)

    with pytest.raises(ValueError, match="config.json has no deposit.source: it names the source"):
        workflow_module._point(workflow, {}, {"deposit.source": None})


# Deliberate change: the jobs of before set apart under every point of the scan,
# those measured at the other value of the scanned setting too.
def test_a_job_of_before_is_set_apart_under_the_point_of_its_own_scanned_values(
    started: list[Any],
    seeded: list[int],
    disk: dict[str, Any],
    ran: list[tuple[str, Any]],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workflow = _counting(ran, monkeypatch)
    execute(workflow, _counted(scan=["amplifier=standard,fast"]))

    execute(workflow, _counted(source="alpha", seed=8))  # both points are of this source now
    points = workflow_module.jobs_of_points(tmp_path / "toy")

    assert [(name, len(jobs), others) for name, _, jobs, others in points] == [
        ("amplifier_fast", 1, [(1, {"source": "beta"})]),
        ("amplifier_standard", 1, [(1, {"source": "beta"})]),
    ]
