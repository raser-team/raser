"""Signal component resolution and dry-run plan."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from raser.apps._planning import WorkflowPlan
from raser.apps._planning import component_selection
from raser.components import load_component
from raser.components import load_source
from raser.core.device import resolve_device
from raser.core.field import FieldConfiguration
from raser.supports.paths import PACKAGE_ROOT
from raser.supports.paths import project_path


CONFIG_PATH = PACKAGE_ROOT / "apps" / "signal" / "signal.json"


def load_defaults() -> dict[str, Any]:
    with CONFIG_PATH.open(encoding="utf-8") as stream:
        return json.load(stream)


def _state(kwargs) -> dict:
    values: dict[str, Any] = {}
    if kwargs.get("voltage") is not None:
        values["bias_voltage"] = float(kwargs["voltage"])
    if kwargs.get("irradiation") is not None:
        values["irradiation"] = {"fluence": float(kwargs["irradiation"])}
    return values


def _work(kwargs) -> dict:
    events = kwargs.get("events_per_job")
    jobs = 1
    scan = kwargs.get("scan")
    if scan is not None:
        if kwargs.get("signal_batch"):
            jobs = int(scan)
        else:
            events = scan
    events = int(1 if events is None else events)
    if events <= 0:
        raise ValueError("Events per job must be positive")
    if jobs <= 0:
        raise ValueError("Job count must be positive")
    return {
        "events_per_job": events,
        "jobs": jobs,
        "seed": int(kwargs.get("seed") or 0),
    }


def build_plan(
    kwargs,
    *,
    g4setup=None,
    workflow: str = "signal",
    default_source: str | None = None,
    default_afe: str | None = None,
) -> WorkflowPlan:
    defaults = load_defaults()
    device = resolve_device(kwargs["det_name"], state=_state(kwargs))
    field = FieldConfiguration.resolve(device)

    source_path, source = load_source(
        kwargs.get("source") or default_source or defaults["source"]
    )
    afe_path, afe = load_component(
        "afe", kwargs.get("amplifier") or default_afe or defaults["afe"]
    )
    if not device.definition.electrical:
        raise ValueError(
            f"Device {device.name} requires electrical values for Frontend"
        )

    components = [
        component_selection("Source", source_path, source),
        component_selection("AFE", afe_path, afe),
    ]
    if g4setup is not None:
        path, values = g4setup
        components.append(component_selection("G4Setup", path, values))

    return WorkflowPlan(
        workflow=workflow,
        device=device.as_dict(),
        field={
            "configuration": field.as_dict(),
            "hash": field.digest,
            "directory": str(field.directory(device)),
        },
        components=tuple(components),
        stages=("Interaction", "Current", "Frontend"),
        output=Path(project_path(workflow)),
        work=_work(kwargs),
    )
