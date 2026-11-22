from __future__ import annotations

import os
import subprocess
import sys
import json
from pathlib import Path

import pytest

from raser.cli.raser import main
from raser.stages import field
from raser.lifecycle import jobs
from raser.supports import process


SOURCE_ROOT = Path(__file__).resolve().parents[2] / "src"


@pytest.fixture
def work_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fields_ready: None
) -> Path:
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

    assert main(["-bb", "signal", "HPK-Si-PiN", "-s", "2", "--seed", "1"]) == 0
    assert main(["-b", "signal", "HPK-Si-PiN", "-s", "2", "--seed", "2", "-mem", "3"]) == 0

    assert submitted == [(True, 2), (True, 3)]


def test_global_test_before_a_command_with_jobs_is_its_dry_run(
    work_root: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    monkeypatch.setattr(
        jobs, "run_indexed_jobs", lambda *args, **kwargs: pytest.fail("submitted")
    )

    assert main(["-t", "-b", "signal", "HPK-Si-PiN", "-s", "2", "--seed", "1"]) == 0

    folder = work_root / "HPK-Si-PiN" / "signal" / "seed_1"
    slices = [
        f"  {name:<15}jobs [0, 1]"
        for name in ("deposit", "field", "current", "readout", "reconstruction")
    ]
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
    first = ["signal", "HPK-Si-PiN", "--scan", "field.voltage=200,300", "-s", "1", "--seed", "1"]
    assert main(first) == 0
    experiment = work_root / "HPK-Si-PiN" / "signal"
    monkeypatch.chdir(experiment)
    capsys.readouterr()

    assert main(["-s", "2", "--seed", "2", "--dry-run"]) == 0
    slices = [
        f"  {name:<15}jobs [0, 1]"
        for name in ("deposit", "field", "current", "readout", "reconstruction")
    ]
    assert capsys.readouterr().out.splitlines() == [
        f"{experiment / 'seed_2'}: jobs [0, 1]",
        *slices,
        f"{experiment / 'voltage_300' / 'seed_2'}: jobs [0, 1]",
        *slices,
    ]
    submitted.clear()
    assert main(["-bb", "-s", "2", "--seed", "3"]) == 0
    every = [
        "--job-slices",
        "deposit,field,current,readout,reconstruction",
    ]  # each voltage is measured anew
    assert submitted == [(["signal", "HPK-Si-PiN", *every], True, 2)] * 2


@pytest.mark.parametrize("command", ["reconstruction", "reco"])
def test_a_stage_command_given_inside_an_experiment_folder_is_not_taken_for_its_options(
    work_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
    command: str,
) -> None:
    experiment = work_root / "HPK-Si-PiN" / "signal"
    experiment.mkdir(parents=True)
    (experiment / "config.json").write_text(
        json.dumps(
            {
                "workflow": "signal",
                "device": "HPK-Si-PiN",
                "field": {"voltage": None, "irradiation_flux": None},
                "deposit": {
                    "source": "decay/Sr90",
                    "g4setup": "device_alone",
                    "events_per_job": 1,
                    "generated_per_job": None,
                    "generated_limit": None,
                    "edep_min": None,
                    "edep_max": None,
                    "fano": True,
                    "plots": 100,
                },
                "current": {"plots": 100},
                "readout": {"amplifier": "SantaCruz+Gali52+Termination50", "sheet_resistance": None},
                "digitizer": {},
                "trigger": {},
                "reconstruction": {
                    "threshold": 10.0,
                    "amplitude_threshold": 10.0,
                    "fractions": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9],
                    "edge": None,
                },
                "analysis": {},
                "names": {},
                "same_seeds": False,
            }
        )
    )
    monkeypatch.chdir(experiment)

    assert main([command, str(experiment), "--seed", "1", "--dry-run"]) == 0

    assert (
        capsys.readouterr().out.splitlines()[0].startswith(f"{experiment / 'seed_1'}: ")
    )


def test_the_version_is_the_one_of_the_package(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    import raser

    monkeypatch.setattr(raser, "__version__", "9.9")

    with pytest.raises(SystemExit):
        main(["--version"])

    assert capsys.readouterr().out.strip() == "raser 9.9"


@pytest.mark.parametrize(
    ("raised", "said"),
    [
        (
            "missing",
            "raser: devsim is not installed. Install it with pip install devsim",
        ),
        (
            "root",
            "raser: ROOT's Python bindings are not available in this Python. "
            "Install them with conda install -c conda-forge root_base",
        ),
    ],
)
def test_a_missing_dependency_is_one_sentence_and_no_traceback(
    work_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
    raised: str,
    said: str,
) -> None:
    from raser.stages import field
    from raser.supports.dependency import MissingDependency

    def execute(*args, **kwargs):
        if raised == "missing":
            raise MissingDependency(
                "devsim is not installed", "Install it with pip install devsim"
            )
        raise ModuleNotFoundError("No module named 'ROOT'", name="ROOT")

    monkeypatch.setattr(field, "execute", execute)

    assert main(["field", "HPK-Si-PiN"]) == 1

    out = capsys.readouterr()
    assert out.err.strip() == said and "Traceback" not in out.err + out.out


def test_another_module_not_found_is_raised_as_it_is(
    work_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from raser.stages import field

    def execute(*args, **kwargs):
        raise ModuleNotFoundError("No module named 'numpyy'", name="numpyy")

    monkeypatch.setattr(field, "execute", execute)

    with pytest.raises(ModuleNotFoundError, match="numpyy"):
        main(["field", "HPK-Si-PiN"])


class _Point:
    def __init__(self, name: str, value: str, dist: str) -> None:
        self.name, self.value = name, value
        self.dist = type("Dist", (), {"name": dist})()


def _registered(monkeypatch: pytest.MonkeyPatch, points: list[_Point]) -> None:
    from raser.cli import raser as cli

    monkeypatch.setattr(
        cli.importlib.metadata,
        "entry_points",
        lambda group: points if group == cli.GROUP else [],
    )


def test_the_experiments_of_the_source_tree_and_of_other_packages_are_commands(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from raser.cli.raser import experiments

    (tmp_path / "pyproject.toml").write_text(
        '[project.entry-points."raser.experiments"]\nsignal = "raser_bench.signal"\n',
        encoding="utf-8",
    )
    # raser installed from this tree as well: its own entry points are those of the tree
    _registered(
        monkeypatch,
        [
            _Point("signal", "raser_bench.signal", "raser"),
            _Point("mine", "my_lab.mine", "my-lab"),
        ],
    )

    assert experiments(tmp_path) == {
        "signal": "raser_bench.signal",
        "mine": "my_lab.mine",
    }
    assert experiments(None) == {"signal": "raser_bench.signal", "mine": "my_lab.mine"}


@pytest.mark.parametrize(
    ("points", "message"),
    [
        (
            [_Point("mine", "a.mine", "lab-a"), _Point("mine", "b.mine", "lab-b")],
            "mine is registered by lab-a and by lab-b",
        ),
        ([_Point("readout", "a.readout", "lab-a")], "readout is a command of raser"),
        ([_Point("rdo", "a.rdo", "lab-a")], "rdo is a command of raser"),
    ],
)
def test_an_experiment_takes_a_name_no_other_command_has(
    monkeypatch: pytest.MonkeyPatch, points: list[_Point], message: str
) -> None:
    from raser.cli.raser import experiments

    _registered(monkeypatch, points)

    with pytest.raises(SystemExit, match=message):
        experiments(None)
