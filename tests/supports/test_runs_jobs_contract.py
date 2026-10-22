from __future__ import annotations

import json
from datetime import datetime
from datetime import timezone
from pathlib import Path

import pytest

from raser.supports import batchjob
from raser.supports.jobs import command_tail
from raser.supports.jobs import plan_indexed_jobs
from raser.supports.jobs import run_indexed_jobs
from raser.supports.runs import latest_run_path
from raser.supports.runs import resolve_configuration
from raser.supports.runs import write_run_record


def test_configuration_precedence_matches_the_run_contract() -> None:
    resolved = resolve_configuration(
        application={"bias": -100.0, "events": 10},
        reusable_defaults={"bias": -200.0, "temperature": 293.0},
        component={"bias": -300.0},
        run_config={"events": 20},
        invocation={"bias": -350.0},
    )
    assert resolved == {"bias": -350.0, "events": 20, "temperature": 293.0}


def test_run_record_is_reserved_once_and_selected_by_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RASER_PROJECT_PATH", str(tmp_path))
    specification = {
        "source": "decay/Sr90",
        "voltage": -300.0,
        "field": "field-hash",
        "device": {"name": "TestPad", "revision": "abc"},
    }
    root, record = write_run_record(
        specification,
        workflow="signal",
        run_id="run-1",
    )

    assert record["workflow"] == "signal"
    assert record["run"] == "run-1"
    assert (root / "batch").is_dir()
    assert not (root / "analysis").exists()
    assert json.loads((root / "run.json").read_text(encoding="utf-8")) == record
    assert (
        latest_run_path(
            "signal",
            source="Sr90",
            voltage=-300.0,
            field="field-hash",
        )
        == root
    )

    with pytest.raises(FileExistsError):
        write_run_record(specification, workflow="signal", run_id="run-1")
    with pytest.raises(ValueError, match="persisted run ID"):
        write_run_record(specification, workflow="signal", run_id="latest")


def test_latest_run_selection_uses_record_creation_time(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class RecordedDateTime:
        values = iter(
            (
                datetime(2026, 1, 1, tzinfo=timezone.utc),
                datetime(2026, 1, 2, tzinfo=timezone.utc),
            )
        )

        @classmethod
        def now(cls, tz):
            assert tz is timezone.utc
            return next(cls.values)

        @staticmethod
        def fromisoformat(value):
            return datetime.fromisoformat(value)

    monkeypatch.setenv("RASER_PROJECT_PATH", str(tmp_path))
    monkeypatch.setattr("raser.supports.runs.datetime", RecordedDateTime)
    specification = {"source": "Sr90", "voltage": 200.0, "field": "field-hash"}
    write_run_record(specification, workflow="signal", run_id="z-earlier")
    _, later = write_run_record(
        specification,
        workflow="signal",
        run_id="a-later",
    )

    selected = latest_run_path(
        "signal",
        source="Sr90",
        voltage=200.0,
        field="field-hash",
    )
    assert selected.name == later["run"]


def test_indexed_and_cluster_plans_preserve_command_tokens(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    tail = command_tail(
        ["signal", "Device A", "--scan", "2", "--dry-run", "--seed=4"],
        ["signal"],
        {"--scan"},
    )
    indexed = plan_indexed_jobs(
        ["signal"],
        tail,
        2,
        use_cluster=False,
        mem=1,
        destination="signal",
    )
    assert indexed.commands == (
        ("signal", "Device A", "--seed=4", "--job", "0"),
        ("signal", "Device A", "--seed=4", "--job", "1"),
    )

    monkeypatch.setenv("RASER_PROJECT_PATH", str(tmp_path))
    plan = batchjob.main(
        "signal",
        ["signal", "Device A", "--job", "0"],
        2,
        is_test=True,
    )
    assert plan.worker_command[-4:] == ("signal", "Device A", "--job", "0")
    assert "hep_sub" in capsys.readouterr().out
    assert not plan.job_file.exists()


def test_partial_cluster_submission_reports_accepted_and_pending_indices(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def submit(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("scheduler rejected job")

    monkeypatch.setattr(batchjob, "main", submit)
    with pytest.raises(
        RuntimeError,
        match=r"accepted indices \[0\]; pending indices \[1, 2\]",
    ):
        run_indexed_jobs(
            ["signal"],
            ["HPK-Si-PiN"],
            3,
            use_cluster=True,
            mem=1,
            destination="signal",
        )
