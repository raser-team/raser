"""Run configuration and run-record helpers."""

from __future__ import annotations

import json
import re
import subprocess
import time
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Any, Mapping

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


def resolve_configuration(
    *,
    application: Mapping[str, Any] | None = None,
    reusable_defaults: Mapping[str, Any] | None = None,
    component: Mapping[str, Any] | None = None,
    run_config: Mapping[str, Any] | None = None,
    invocation: Mapping[str, Any] | None = None,
):
    """Resolve values from broad defaults to one invocation."""
    resolved = {}
    for layer in (
        application,
        reusable_defaults,
        component,
        run_config,
        invocation,
    ):
        if layer:
            resolved.update(
                {key: value for key, value in layer.items() if value is not None}
            )
    return resolved


def new_run_id():
    return time.strftime("%Y_%m%d_%H%M%S") + f"_{time.time_ns() % 1_000_000:06d}"


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


def write_run_record(
    specification: Mapping[str, Any],
    *,
    workflow: str,
    run_id: str | None = None,
) -> tuple[Path, dict[str, Any]]:
    if not workflow or _slug(workflow) != workflow:
        raise ValueError(f"Invalid workflow name: {workflow}")
    allocated_id = run_id or new_run_id()
    if allocated_id == "latest" or _slug(allocated_id) != allocated_id:
        raise ValueError(f"Invalid persisted run ID: {allocated_id}")

    record = dict(specification)
    record.update(
        {
            "workflow": workflow,
            "run": allocated_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "git": git_metadata(),
        }
    )
    payload = json.dumps(record, indent=2, sort_keys=True) + "\n"

    root = run_path(workflow, allocated_id)
    root.mkdir(parents=True, exist_ok=False)
    (root / "batch").mkdir()
    record_path = root / "run.json"
    record_path.write_text(payload, encoding="utf-8")
    return root, record


def latest_run_path(workflow, source=None, voltage=None, field=None):
    base = project_path(workflow)
    candidates = []
    for run_json in base.glob("**/run.json"):
        with open(run_json) as file:
            record = json.load(file)
        if source is not None and source_name(record.get("source")) != source_name(
            source
        ):
            continue
        if voltage is not None and float(record.get("voltage")) != float(voltage):
            continue
        if field is not None and record.get("field") != field:
            continue
        try:
            created_at = datetime.fromisoformat(record["created_at"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Run record has invalid created_at: {run_json}") from exc
        candidates.append((created_at, run_json.parent))
    if not candidates:
        raise FileNotFoundError(f"No runs found under {base}")
    candidates.sort(key=lambda item: item[0])
    latest_time = candidates[-1][0]
    latest = [path for created_at, path in candidates if created_at == latest_time]
    if len(latest) != 1:
        raise ValueError(f"Latest run selection is ambiguous under {base}")
    return latest[0]


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

    record = {
        "sensor": detector.det_name,
        "source": source,
        "field": field_set,
        "field_set": field_set,
        "field_source": field_source,
        "voltage": float(voltage),
        "events_per_job": int(
            kwargs.get("events_per_job") or config.get("events_per_job", 0) or 0
        ),
        "jobs": kwargs.get("scan"),
        "amplifier": getattr(detector, "amplifier", None),
        "daq": getattr(detector, "daq", None),
    }
    root, record = write_run_record(record, workflow=workflow, run_id=run_id)
    batch = root / "batch"
    kwargs["_run_path"] = str(root)
    kwargs["_run_batch_path"] = str(batch)
    kwargs["_field_set"] = field_set
    kwargs["_field_source"] = field_source
    return record
