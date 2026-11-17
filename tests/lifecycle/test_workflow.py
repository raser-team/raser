from __future__ import annotations

import argparse
import errno
import json
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


def test_a_scan_runs_every_value_and_only_values_that_differ_get_a_folder(
    started: list[Any], disk: dict[str, Any], tmp_path: Path
) -> None:
    scan = ["voltage=200,300"]

    execute(BIASED, _kwargs(det_name="dev", voltage=None, scan=scan, jobs=2))

    experiment = tmp_path / "toy"
    assert _folders(started, experiment) == ["seed_42", "voltage_300/seed_42"]
    assert _record(experiment / "seed_42")["options"]["voltage"] == 200
    assert _record(experiment / "voltage_300" / "seed_42")["options"]["voltage"] == 300


def test_a_scanned_address_is_written_into_the_file_of_each_point_that_differs(
    started: list[Any], disk: dict[str, Any], tmp_path: Path
) -> None:
    scan = ["device.bias.voltage=200,300"]

    execute(TOY_DEVICE, _kwargs(det_name="dev", scan=scan, jobs=2))

    experiment = tmp_path / "toy"
    assert _folders(started, experiment) == ["seed_42", "bias.voltage_300/seed_42"]
    unscanned = _record(experiment / "seed_42")
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

    assert _folders(started, experiment) == ["seed_42", "bias_300/seed_42"]
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
        "seed_42",
        "spare_2/seed_42",
        "bias.voltage_300/seed_42",
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


def test_two_scanned_options_give_every_combination_named_by_what_differs(
    started: list[Any], tmp_path: Path
) -> None:
    scan = ["gain=5,7", "width=1.0,2.0"]

    execute(GAIN, _kwargs(gain=None, width=None, scan=scan, jobs=2))

    assert _folders(started, tmp_path / "toy") == [
        "seed_42",
        "width_2/seed_42",
        "gain_7/seed_42",
        "gain_7_width_2/seed_42",
    ]


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
        "seed_1",
        "gain_7/seed_1",
        "seed_2",
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
        ("", 200, [0, 1]),
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
        ("", 5, ["seed_1:0", "seed_1:1", "seed_2:0"]),
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
    for point in ("", "gain_7"):
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
        str(experiment),
        str(experiment / "x_2"),
    ] * 2
    assert "seed" not in received[0]
    assert _record(experiment / "x_2") == {
        "point": "x_2", "commit": "abc", "options": {"x": 2}, "files": {},
    }
    assert "same_seeds" not in json.loads((experiment / "config.json").read_text())
    assert [(name, len(done)) for name, _, done in
            workflow_module.finished(workflow, _plain(), experiment)] == [("", 1), ("x_2", 1)]


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
    assert [(name, len(done)) for name, _, done in points] == [("", 1), ("seed_layer_2", 1)]


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
        ["toy", "--job-dir", str(experiment / name)] for name in ("", "x_2", "x_3")
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


def test_under_another_commit_every_slice_runs_again_and_the_old_run_is_kept(
    started: list[Any],
    seeded: list[int],
    disk: dict[str, Any],
    ran: list[tuple[str, Any]],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    execute(_chain(ran), _chain_kwargs())
    del ran[:]
    monkeypatch.setattr(workflow_module, "_commit", lambda: "def")

    execute(_chain(ran), _chain_kwargs())

    assert ran == [("deposits", "beta"), ("currents", 200.0), ("waveforms", "standard")]
    assert len(_kept(tmp_path / "toy")) == 1


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
    assert _marks(experiment / "seed_42") == [
        "currents_0.done",
        "deposits_0.done",
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


def test_a_slice_is_told_the_batch_folder_of_every_slice(
    started: list[Any], seeded: list[int], disk: dict[str, Any], tmp_path: Path
) -> None:
    told: list[tuple[str, Any, dict[str, str], int]] = []

    def piece(name: str, key: str) -> Slice:
        def run(options: dict[str, Any]) -> None:
            told.append((name, options[key], options["_slice_batch_paths"], options["seed"]))

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
    assert told[1][2] == {
        "deposits": str(experiment / "seed_42" / "batch"),
        "currents": str(experiment / "voltage_300" / "seed_42" / "batch"),
    }
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


def test_a_file_system_that_cannot_lock_warns_and_lets_the_run_go_on(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def refuse(handle, how):
        raise OSError(errno.ENOLCK, "No locks available")

    monkeypatch.setattr(workflow_module.fcntl, "flock", refuse)

    assert workflow_module._lock(tmp_path / "x.lock", "x") is None
    assert "cannot be locked here (No locks available)" in capsys.readouterr().out
