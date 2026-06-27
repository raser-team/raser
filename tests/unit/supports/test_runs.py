from types import SimpleNamespace
import json

from raser.supports import runs


def test_apply_run_config_fills_missing_values(monkeypatch):
    monkeypatch.setattr(
        runs,
        "load_run_config",
        lambda name=None: {
            "source": "decay/Sr90",
            "field": "default",
            "events_per_job": 10000,
        },
    )
    kwargs = {"source": None, "field": None, "events_per_job": None, "scan": None}

    runs.apply_run_config(kwargs)

    assert kwargs["source"] == "decay/Sr90"
    assert kwargs["field"] == "default"
    assert kwargs["events_per_job"] == 10000
    assert kwargs["scan"] is None


def test_ensure_run_id_generates_timestamp(monkeypatch):
    monkeypatch.setattr(runs.time, "strftime", lambda fmt: "2026_0627_044005")
    kwargs = {"run": None}

    assert runs.ensure_run_id(kwargs) == "2026_0627_044005"
    assert kwargs["run"] == "2026_0627_044005"


def test_prepare_run_record_groups_by_metadata(tmp_path, monkeypatch):
    monkeypatch.setenv("RASER_PROJECT_PATH", str(tmp_path))
    monkeypatch.setattr(
        runs,
        "git_metadata",
        lambda: {"commit": "abc123", "dirty": True},
    )
    kwargs = {
        "workflow": "timeres",
        "source": "decay/Sr90",
        "field": "tcad_500V",
        "voltage": -500,
        "run": "2026_0627_044005",
        "scan": 10,
        "events_per_job": None,
        "_run_config": {"events_per_job": 10000},
    }
    detector = SimpleNamespace(
        det_name="NJU-PiN",
        field_source="NJU-PiN",
        voltage=-500.0,
        amplifier="Broad_Band_UCSC",
        daq="NJU-PiN",
    )

    record = runs.prepare_run_record(kwargs, detector)

    expected = tmp_path / "timeres" / "2026_0627_044005"
    assert expected.is_dir()
    assert (expected / "batch").is_dir()
    assert (expected / "run.json").is_file()
    assert kwargs["_run_path"] == str(expected)
    assert kwargs["_run_batch_path"] == str(expected / "batch")
    assert record["events_per_job"] == 10000
    assert record["field"] == "tcad_500V"
    assert record["field_set"] == "tcad_500V"
    assert record["field_source"] == "NJU-PiN"
    assert record["git"] == {"commit": "abc123", "dirty": True}


def test_prepare_run_record_records_default_field_set(tmp_path, monkeypatch):
    monkeypatch.setenv("RASER_PROJECT_PATH", str(tmp_path))
    kwargs = {
        "workflow": "signal",
        "source": "decay/Am241",
        "field": "default",
        "voltage": 200,
        "run": "2026_0627_044006",
        "scan": None,
        "events_per_job": 1,
        "_run_config": {"events_per_job": 1},
    }
    detector = SimpleNamespace(
        det_name="HPK-Si-PiN",
        field_source="HPK-Si-PiN",
        voltage=200.0,
        amplifier="Broad_Band_UCSC",
        daq="Alibava",
    )

    record = runs.prepare_run_record(kwargs, detector)

    expected = tmp_path / "signal" / "2026_0627_044006"
    assert expected.is_dir()
    assert kwargs["_run_path"] == str(expected)
    assert record["events_per_job"] == 1
    assert record["field"] == "default"
    assert record["field_set"] == "default"
    assert record["field_source"] == "HPK-Si-PiN"


def test_latest_run_path_filters_by_run_metadata(tmp_path, monkeypatch):
    monkeypatch.setenv("RASER_PROJECT_PATH", str(tmp_path))
    old_run = tmp_path / "signal" / "2026_0627_044005"
    new_run = tmp_path / "signal" / "2026_0627_044006"
    other_voltage = tmp_path / "signal" / "2026_0627_044007"
    for path, voltage in ((old_run, 200), (new_run, 200), (other_voltage, 300)):
        path.mkdir(parents=True)
        with open(path / "run.json", "w") as file:
            json.dump(
                {"source": "decay/Am241", "field": "default", "voltage": voltage},
                file,
            )

    assert runs.latest_run_path("signal", "decay/Am241", voltage=200) == new_run
