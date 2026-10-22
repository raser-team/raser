"""Field command planning and legacy execution adapters."""

from __future__ import annotations

import json
import logging
import subprocess
import sys

from raser.core.device import resolve_device

from .configuration import FieldPlan
from .configuration import plan_field


def _configure_logging(verbose: int) -> None:
    if verbose == 1:
        logging.basicConfig(level=logging.INFO)
    elif verbose >= 2:
        logging.basicConfig(level=logging.DEBUG)


def _field_replacements(kwargs) -> dict:
    replacements = {}
    if kwargs.get("bias") is not None:
        replacements["bias_voltage"] = kwargs["bias"]
    if kwargs.get("irradiation_flux") is not None:
        replacements["irradiation"] = {"fluence": kwargs["irradiation_flux"]}
    if kwargs.get("input") is not None:
        replacements["converter"] = {"flip": bool(kwargs.get("flip"))}
    return replacements


def build_plan(kwargs) -> FieldPlan:
    device = resolve_device(kwargs["target"])
    action = "import" if kwargs.get("input") is not None else "solve"
    if action == "solve" and kwargs.get("wf"):
        action = "weight"
    replacements = _field_replacements(kwargs)
    if action == "import":
        replacements["source"] = "tcad"
    return plan_field(
        action,
        device,
        replacements=replacements,
        input_path=kwargs.get("input"),
    )


def _show(plan: FieldPlan) -> None:
    print(json.dumps(plan.as_dict(), indent=2, sort_keys=True))


def _prepare_execution(plan: FieldPlan, kwargs) -> None:
    values = plan.configuration.values
    kwargs["target"] = str(plan.device.definition.source_path)
    kwargs["bias"] = float(values["bias_voltage"])
    kwargs["irradiation_flux"] = values.get("irradiation", {}).get("fluence")
    kwargs["_field_directory"] = str(plan.directory)
    kwargs["_field_configuration"] = plan.configuration.as_dict()


def solve(kwargs):
    _configure_logging(kwargs.get("verbose", 0))
    plan = build_plan(kwargs)
    if kwargs.get("dry_run"):
        _show(plan)
        return plan
    plan.configuration.write(plan.device)
    _prepare_execution(plan, kwargs)
    if kwargs.get("umf"):
        from . import solver_section

        subprocess.run(
            [
                sys.executable,
                "-mdevsim.umfpack.umfshim",
                str(solver_section.__file__),
                repr(str(kwargs)),
            ],
            check=True,
        )
    else:
        from . import solver_section

        solver_section.main(kwargs)
    return plan


def import_field(kwargs):
    _configure_logging(kwargs.get("verbose", 0))
    plan = build_plan(kwargs)
    if kwargs.get("dry_run"):
        _show(plan)
        return plan
    plan.configuration.write(plan.device)
    _prepare_execution(plan, kwargs)
    from . import extract_from_tcad

    extract_from_tcad.main(
        str(plan.input_path),
        str(plan.device.definition.source_path),
        plan.directory,
        plan.configuration.values["bias_voltage"],
        is_flip=kwargs.get("flip", False),
    )
    return plan


def weight(kwargs):
    kwargs["wf"] = True
    plan = build_plan(kwargs)
    if kwargs.get("dry_run"):
        _show(plan)
        return plan
    plan.configuration.write(plan.device)
    _prepare_execution(plan, kwargs)
    from . import solver_section

    solver_section.main(kwargs)
    return plan


def main(kwargs):
    if kwargs.get("input") is not None:
        return import_field(kwargs)
    return solve(kwargs)
