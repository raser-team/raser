from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from raser.lifecycle import jobs
from raser.lifecycle import workflow as workflow_module
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

    monkeypatch.setattr(jobs, "run_indexed_jobs", run_indexed_jobs)
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

    def load_definition(selector: str) -> SimpleNamespace:
        bias = {"electrode": "top", "voltage": 200.0}
        return SimpleNamespace(raw={"det_name": selector, "bias": bias, **content})

    monkeypatch.setattr(workflow_module, "load_component", load_component)
    monkeypatch.setattr(workflow_module, "load_definition", load_definition)
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


def _summary(experiment: Path) -> list[dict[str, str]]:
    with (experiment / "summary.csv").open(newline="") as stream:
        return list(csv.DictReader(stream))


def _counting(received: list[Any]) -> Workflow:
    def extract(point: Path, done: list[tuple[Path, int]]) -> dict[str, Any]:
        received.append((point, done))
        return {"seeds": len({folder for folder, _ in done})}

    return Workflow(
        name="toy",
        job=lambda options: None,
        keys=("gain", "width"),
        defaults={"gain": 5, "width": 1.0},
        device=False,
        extract=extract,
    )


def test_the_summary_has_a_row_per_point_from_all_its_seed_folders(
    started: list[Any], tmp_path: Path
) -> None:
    workflow = _counting([])
    scan = ["gain=5,7"]

    execute(workflow, _kwargs(gain=None, width=None, scan=scan, seed=1, jobs=2))
    execute(workflow, _kwargs(gain=None, width=None, scan=scan, seed=2, jobs=3))

    assert _summary(tmp_path / "toy") == [
        {"point": ".", "gain": "5", "jobs": "5", "seeds": "2"},
        {"point": "gain_7", "gain": "7", "jobs": "5", "seeds": "2"},
    ]


def test_the_summary_leaves_out_seed_folders_that_ran_with_another_record(
    started: list[Any], tmp_path: Path
) -> None:
    received: list[Any] = []
    workflow = _counting(received)
    execute(workflow, _kwargs(gain=None, width=None, seed=1, jobs=2))
    execute(workflow, _kwargs(gain=None, width=None, seed=2, jobs=2))

    execute(workflow, _kwargs(gain=None, width=2.0, seed=1, jobs=2))

    experiment = tmp_path / "toy"
    point, done = received[-1]
    assert point == experiment
    assert done == [(experiment / "seed_1", 0), (experiment / "seed_1", 1)]
    assert _summary(experiment) == [{"point": ".", "jobs": "2", "seeds": "1"}]


def test_the_summary_leaves_out_a_folder_kept_aside_with_the_same_record(
    started: list[Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(workflow_module, "_commit", lambda: "abc+dirty")
    workflow = _counting([])

    execute(workflow, _kwargs(gain=None, width=None, seed=1, jobs=2))
    execute(workflow, _kwargs(gain=None, width=None, seed=1, jobs=2))

    assert _summary(tmp_path / "toy") == [{"point": ".", "jobs": "2", "seeds": "1"}]


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
