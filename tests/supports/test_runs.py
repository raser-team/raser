from __future__ import annotations

import json
from datetime import datetime
from datetime import timezone
from pathlib import Path

import pytest

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
        "components": [{"kind": "Source", "name": "Sr90", "path": "decay/Sr90.json"}],
        "field": {"hash": "field-hash"},
        "device": {
            "name": "TestPad",
            "revision": "abc",
            "state": {"bias_voltage": -300.0},
        },
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
    assert latest_run_path("signal", specification=specification) == root

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
    specification = {
        "components": [{"kind": "Source", "name": "Sr90", "path": "decay/Sr90.json"}],
        "device": {"state": {"bias_voltage": 200.0}},
        "field": {"hash": "field-hash"},
    }
    write_run_record(specification, workflow="signal", run_id="z-earlier")
    _, later = write_run_record(
        specification,
        workflow="signal",
        run_id="a-later",
    )

    selected = latest_run_path("signal", specification=specification)
    assert selected.name == later["run"]
