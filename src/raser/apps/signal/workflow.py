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
    events = int(kwargs.get("events_per_job") or 1)
    if events <= 0:
        raise ValueError("Events per job must be positive")
    jobs = int(kwargs.get("scan") or 1)
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

    device = resolve_device(
        kwargs["det_name"],
        state=_state(kwargs),
    )

    field = FieldConfiguration.from_device(device)

    # 默认使用当前配置计算出的 Field 目录
    field_directory = field.directory(device)
    field_selector = field.digest

    # 如果命令行指定 --field，则强制使用指定 Field 目录
    requested_field = kwargs.get("field")
    if requested_field and str(requested_field).lower() != "default":
        requested_field = str(requested_field)

        candidate = Path(requested_field).expanduser()
        if not candidate.is_absolute():
            candidate = project_path("field", requested_field)

        candidate = candidate.resolve()

        if not candidate.is_dir():
            raise FileNotFoundError(
                f"指定的 Field 目录不存在: {candidate}"
            )

        field_directory = candidate
        field_selector = requested_field

    source_path, source = load_source(
        kwargs.get("source")
        or default_source
        or defaults["source"]
    )

    afe_path, afe = load_component(
        "afe",
        kwargs.get("amplifier")
        or default_afe
        or defaults["afe"],
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
        components.append(
            component_selection("G4Setup", path, values)
        )

    return WorkflowPlan(
        workflow=workflow,
        device=device.as_dict(),
        field={
            "configuration": field.as_dict(),
            "hash": field_selector,
            "directory": str(field_directory),
        },
        components=tuple(components),
        stages=("Interaction", "Current", "Frontend"),
        output=Path(project_path(workflow)),
        work=_work(kwargs),
    )
# def build_plan(
#     kwargs,
#     *,
#     g4setup=None,
#     workflow: str = "signal",
#     default_source: str | None = None,
#     default_afe: str | None = None,
# ) -> WorkflowPlan:
#     defaults = load_defaults()
#     device = resolve_device(kwargs["det_name"], state=_state(kwargs))
#     field = FieldConfiguration.from_device(device)

#     source_path, source = load_source(
#         kwargs.get("source") or default_source or defaults["source"]
#     )
#     afe_path, afe = load_component(
#         "afe", kwargs.get("amplifier") or default_afe or defaults["afe"]
#     )
#     if not device.definition.electrical:
#         raise ValueError(
#             f"Device {device.name} requires electrical values for Frontend"
#         )

#     components = [
#         component_selection("Source", source_path, source),
#         component_selection("AFE", afe_path, afe),
#     ]
#     if g4setup is not None:
#         path, values = g4setup
#         components.append(component_selection("G4Setup", path, values))

#     return WorkflowPlan(
#         workflow=workflow,
#         device=device.as_dict(),
#         field={
#             "configuration": field.as_dict(),
#             "hash": field.digest,
#             "directory": str(field.directory(device)),
#         },
#         components=tuple(components),
#         stages=("Interaction", "Current", "Frontend"),
#         output=Path(project_path(workflow)),
#         work=_work(kwargs),
#     )
