"""Project workspace commands."""

from __future__ import annotations

import shutil

from raser.supports.output import create_path
from raser.supports.paths import DEFAULT_COMPONENT_ROOT
from raser.supports.paths import app_component_root
from raser.supports.paths import work_root


APP_TEMPLATES = {
    "bmos": ("bmos",),
    "cce": ("cce", "signal"),
    "lumi": ("lumi",),
    "signal": ("signal",),
    "tct": ("tct",),
    "telescope": ("telescope",),
    "timeres": ("timeres", "signal"),
}


def _copy_components(source, destination):
    if source.exists():
        shutil.copytree(source, destination, dirs_exist_ok=True)


def create_project(name, template=None):
    destination = work_root() / name
    create_path(destination)
    component_destination = destination / "components"
    create_path(component_destination)

    _copy_components(DEFAULT_COMPONENT_ROOT, component_destination)
    for app_name in APP_TEMPLATES.get(template or "", ()):
        _copy_components(app_component_root(app_name), component_destination)

    return destination


def main(kwargs):
    action = kwargs["project_action"]
    if action == "create":
        destination = create_project(kwargs["project_name"], kwargs.get("template"))
        print(destination)
    else:
        raise NameError(action)
