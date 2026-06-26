"""Run configuration and run-record helpers."""

from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path

from raser.supports.output import create_path
from raser.supports.paths import project_path


def load_run_config(name: str | None = None):
    if name is None:
        return {}
    config_name = name
    if Path(config_name).suffix:
        config_path = Path(config_name)
    else:
        config_path = project_path("config", config_name + ".json")
    with open(config_path) as file:
        return json.load(file)


def apply_run_config(kwargs):
    config = load_run_config(kwargs.get("config"))
    for key in ("source", "field", "events_per_job"):
        if kwargs.get(key) is None and key in config:
            kwargs[key] = config[key]
    kwargs["_run_config"] = config
    return config


def new_run_id():
    return time.strftime("%Y_%m%d_%H%M%S")


def ensure_run_id(kwargs):
    run_id = kwargs.get("run")
    if run_id in (None, "latest"):
        run_id = new_run_id()
        kwargs["run"] = run_id
    return run_id


def source_name(source):
    return Path(str(source)).stem


def _slug(value):
    return re.sub(r"[^A-Za-z0-9_.+-]+", "_", str(value))


def resolve_field_source(kwargs, detector):
    return getattr(detector, "field_source", detector.det_name)


def resolve_field_set(kwargs, config):
    return kwargs.get("field") or config.get("field") or "default"


def run_path(workflow, run_id):
    return project_path(
        workflow,
        _slug(run_id),
    )


def latest_run_path(workflow, source=None, voltage=None, field=None):
    base = project_path(workflow)
    candidates = []
    for run_json in base.glob("**/run.json"):
        with open(run_json) as file:
            record = json.load(file)
        if source is not None and source_name(record.get("source")) != source_name(source):
            continue
        if voltage is not None and float(record.get("voltage")) != float(voltage):
            continue
        if field is not None and record.get("field") != field:
            continue
        candidates.append(run_json.parent)
    if not candidates:
        raise FileNotFoundError(f"No runs found under {base}")
    return sorted(candidates)[-1]


def git_metadata():
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--short"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {"commit": None, "dirty": None}
    return {"commit": commit, "dirty": bool(status.strip())}


def prepare_run_record(kwargs, detector):
    config = kwargs.get("_run_config") or apply_run_config(kwargs)
    workflow = kwargs.get("workflow") or kwargs.get("signal_output_label") or "signal"
    source = kwargs.get("source") or config.get("source")
    field_set = resolve_field_set(kwargs, config)
    voltage = kwargs.get("voltage")
    if voltage is None:
        voltage = detector.voltage
    run_id = ensure_run_id(kwargs)
    field_source = resolve_field_source(kwargs, detector)

    root = run_path(workflow, run_id)
    batch = root / "batch"
    create_path(batch)
    record = {
        "workflow": workflow,
        "sensor": detector.det_name,
        "source": source,
        "field": field_set,
        "field_set": field_set,
        "field_source": field_source,
        "voltage": float(voltage),
        "events_per_job": int(kwargs.get("events_per_job") or config.get("events_per_job", 0) or 0),
        "jobs": kwargs.get("scan"),
        "amplifier": getattr(detector, "amplifier", None),
        "daq": getattr(detector, "daq", None),
        "run": run_id,
        "git": git_metadata(),
    }
    with open(root / "run.json", "w") as file:
        json.dump(record, file, indent=2, sort_keys=True)
        file.write("\n")
    kwargs["_run_path"] = str(root)
    kwargs["_run_batch_path"] = str(batch)
    kwargs["_field_set"] = field_set
    kwargs["_field_source"] = field_source
    return record
