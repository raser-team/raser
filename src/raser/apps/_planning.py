"""Serializable application plans used by dry-run execution."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from raser.supports import runs


def execution_seed(kwargs: Mapping[str, Any], *, offset: int = 0) -> int:
    seed = int(kwargs.get("seed") or 0) + int(offset)
    if seed < 0:
        raise ValueError("Run seed must be non-negative")
    return seed


@dataclass(frozen=True)
class ComponentSelection:
    kind: str
    name: str
    path: Path
    values: Mapping[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "name": self.name,
            "path": str(self.path),
            "values": dict(self.values),
        }


@dataclass(frozen=True)
class WorkflowPlan:
    workflow: str
    device: Mapping[str, Any]
    field: Mapping[str, Any]
    components: tuple[ComponentSelection, ...]
    stages: tuple[str, ...]
    output: Path
    work: Mapping[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "workflow": self.workflow,
            "device": dict(self.device),
            "field": dict(self.field),
            "components": [component.as_dict() for component in self.components],
            "stages": list(self.stages),
            "output": str(self.output),
            "work": dict(self.work),
        }

    def show(self) -> None:
        print(json.dumps(self.as_dict(), indent=2, sort_keys=True))


def component_selection(
    kind: str, path: Path, values: Mapping[str, Any]
) -> ComponentSelection:
    name = str(values.get("name") or values.get("laser_model") or path.stem)
    return ComponentSelection(kind, name, path.resolve(), values)


def activate_plan(plan: WorkflowPlan, kwargs: dict[str, Any]) -> dict[str, Any]:
    run_id = runs.ensure_run_id(kwargs)
    root = runs.run_path(plan.workflow, run_id)
    record_path = root / "run.json"
    specification = plan.as_dict()
    if record_path.is_file():
        record = json.loads(record_path.read_text(encoding="utf-8"))
        for name in ("workflow", "device", "field", "components", "stages"):
            if record.get(name) != specification.get(name):
                raise ValueError(f"Run {run_id} has a different {name} specification")
    else:
        root, record = runs.write_run_record(
            specification,
            workflow=plan.workflow,
            run_id=run_id,
        )

    kwargs["_run_path"] = str(root)
    kwargs["_run_batch_path"] = str(root / "batch")
    kwargs["_field_set"] = plan.field["hash"]
    kwargs["_field_directory"] = plan.field["directory"]
    kwargs["_field_source"] = plan.field["configuration"]["source"]
    kwargs["_workflow_plan"] = plan
    return record
