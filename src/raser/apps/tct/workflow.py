"""TCT component resolution and dry-run plan."""

from __future__ import annotations

import json
from pathlib import Path

from raser.apps._planning import ComponentSelection
from raser.apps._planning import WorkflowPlan
from raser.apps._planning import component_selection
from raser.components import load_component
from raser.components import load_laser
from raser.core.device import resolve_device
from raser.core.field import FieldConfiguration
from raser.supports.paths import PACKAGE_ROOT
from raser.supports.paths import project_path


CONFIG_PATH = PACKAGE_ROOT / "apps" / "tct" / "transient_current.json"


def load_defaults():
    with CONFIG_PATH.open(encoding="utf-8") as stream:
        return json.load(stream)


def _component(plan: WorkflowPlan, kind: str) -> ComponentSelection:
    matches = [component for component in plan.components if component.kind == kind]
    if len(matches) != 1:
        raise ValueError(f"{plan.workflow} requires one {kind} component")
    return matches[0]


def runtime_components(kwargs):
    plan = kwargs.get("_workflow_plan")
    if not isinstance(plan, WorkflowPlan):
        raise RuntimeError("TCT requires an activated workflow plan")
    laser = _component(plan, "Laser")
    afe = _component(plan, "AFE")
    return dict(laser.values), afe.name


def build_plan(kwargs) -> WorkflowPlan:
    defaults = load_defaults()
    state = {}
    if kwargs.get("voltage") is not None:
        state["bias_voltage"] = float(kwargs["voltage"])
    device = resolve_device(kwargs["det_name"], state=state)
    field = FieldConfiguration.from_device(device)
    laser_path, laser = load_laser(kwargs["laser"])
    afe_path, afe = load_component(
        "afe", kwargs.get("amplifier") or defaults["amplifier"]
    )
    if not device.definition.electrical:
        raise ValueError(
            f"Device {device.name} requires electrical values for Frontend"
        )

    mode = kwargs.get("tct_mode") or "signal"
    stages = ["Interaction", "Current", "Frontend"]
    if mode.startswith("position"):
        stages.append("Position analysis")
    return WorkflowPlan(
        workflow="tct",
        device=device.as_dict(),
        field={
            "configuration": field.as_dict(),
            "hash": field.digest,
            "directory": str(field.directory(device)),
        },
        components=(
            component_selection("Laser", laser_path, laser),
            component_selection("AFE", afe_path, afe),
        ),
        stages=tuple(stages),
        output=Path(project_path("tct")),
        work={
            "jobs": int(kwargs.get("scan") or 1),
            "seed": int(kwargs.get("seed") or 0),
        },
    )
