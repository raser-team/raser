from __future__ import annotations

from pathlib import Path

import pytest

from raser.lifecycle import scheduler


COMMAND = ["signal", "run"]


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A project given by a relative path, as a user running in place has it."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("RASER_PROJECT_PATH", "project")
    monkeypatch.delenv("RASER_SCHEDULER", raising=False)
    monkeypatch.delenv("RASER_CONDOR_JOB_FLAVOUR", raising=False)
    monkeypatch.delenv("RASER_SUBMIT_QUEUE", raising=False)
    monkeypatch.delenv("RASER_ENV_ROUTE", raising=False)
    return tmp_path / "project"


@pytest.fixture
def submitted(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, ...]]:
    commands: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        scheduler.subprocess,
        "run",
        lambda command, **kwargs: commands.append(tuple(command)),
    )
    return commands


def _description(plan: scheduler.ClusterJobPlan) -> dict[str, str]:
    assert plan.submit_description is not None
    pairs = (line.split(" = ", 1) for line in plan.submit_description.splitlines())
    return {pair[0]: pair[1] for pair in pairs if len(pair) == 2}


def test_condor_memory_request_scales_with_the_batch_level(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RASER_SCHEDULER", "condor")

    requests = [
        _description(scheduler.plan_job("signal", COMMAND, level))["request_memory"]
        for level in (1, 3)
    ]

    assert requests == ["8000", "24000"]


def test_condor_flavour_is_the_requested_one_and_unknown_ones_stop_before_writing(
    project: Path, monkeypatch: pytest.MonkeyPatch, submitted: list
) -> None:
    monkeypatch.setenv("RASER_SCHEDULER", "condor")

    default = _description(scheduler.plan_job("signal", COMMAND, 1))
    monkeypatch.setenv("RASER_CONDOR_JOB_FLAVOUR", "espresso")
    chosen = _description(scheduler.plan_job("signal", COMMAND, 1))
    monkeypatch.setenv("RASER_CONDOR_JOB_FLAVOUR", "bananas")
    with pytest.raises(ValueError, match="bananas"):
        scheduler.main("signal", COMMAND, 1)

    assert default["+JobFlavour"] == '"workday"'
    assert chosen["+JobFlavour"] == '"espresso"'
    assert not project.exists()
    assert submitted == []


@pytest.mark.parametrize(
    ("setting", "program"),
    [(None, "hep_sub"), ("hep_sub", "hep_sub"), ("condor", "condor_submit")],
)
def test_scheduler_setting_selects_the_submit_program(
    project: Path,
    monkeypatch: pytest.MonkeyPatch,
    setting: str | None,
    program: str,
) -> None:
    if setting is not None:
        monkeypatch.setenv("RASER_SCHEDULER", setting)

    plan = scheduler.plan_job("signal", COMMAND, 1, group="physics")

    assert plan.submit_command[0] == program
    assert (plan.submit_file is not None) == (program == "condor_submit")


def test_unknown_scheduler_stops_before_writing(
    project: Path, monkeypatch: pytest.MonkeyPatch, submitted: list
) -> None:
    monkeypatch.setenv("RASER_SCHEDULER", "not-a-scheduler")

    with pytest.raises(ValueError, match="not-a-scheduler"):
        scheduler.main("signal", COMMAND, 1)

    assert not project.exists()
    assert submitted == []


def test_condor_submission_hands_over_a_description_with_absolute_paths(
    project: Path, monkeypatch: pytest.MonkeyPatch, submitted: list
) -> None:
    monkeypatch.setenv("RASER_SCHEDULER", "condor")

    plan = scheduler.main("signal", COMMAND, 1)

    assert plan.submit_file is not None
    assert submitted == [("condor_submit", str(plan.submit_file))]
    written = plan.submit_file.read_text(encoding="utf-8")
    assert written == plan.submit_description + "\n"
    description = _description(plan)
    jobs = project / "signal" / "jobs"
    assert Path(description["executable"]) == jobs / plan.job_file.name
    assert Path(description["executable"]).is_file()
    for key in ("output", "error", "log"):
        assert Path(description[key]).parent == jobs


def test_condor_test_mode_writes_and_submits_nothing(
    project: Path, monkeypatch: pytest.MonkeyPatch, submitted: list
) -> None:
    monkeypatch.setenv("RASER_SCHEDULER", "condor")

    scheduler.main("signal", COMMAND, 1, is_test=True)

    assert not project.exists()
    assert submitted == []


def test_an_installed_raser_records_its_version_and_runs_its_workers_in_the_folder_of_the_command(
    tmp_path, monkeypatch
) -> None:
    from raser.lifecycle import workflow

    monkeypatch.setattr(workflow, "REPO_ROOT", None)
    monkeypatch.setattr(workflow.importlib.metadata, "version", lambda name: "5.0")
    assert workflow._commit() == "raser 5.0"

    monkeypatch.setattr(scheduler, "REPO_ROOT", None)
    monkeypatch.chdir(tmp_path)
    script = scheduler.worker_script(("raser", "signal", "dev"), None)
    assert f"cd {tmp_path} || exit 1" in script and "env/setup" not in script
