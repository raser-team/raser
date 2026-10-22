"""Charge-collection setup resolution and dry-run plan."""

from __future__ import annotations

import json

from raser.apps._planning import WorkflowPlan
from raser.apps._planning import component_selection
from raser.apps.signal.workflow import build_plan as build_signal_plan
from raser.components import load_component
from raser.supports.paths import PACKAGE_ROOT
from raser.supports.paths import app_component_roots
from raser.supports.paths import component_path


CONFIG_PATH = PACKAGE_ROOT / "apps" / "cce" / "charge_collection.json"


def load_defaults():
    with CONFIG_PATH.open(encoding="utf-8") as stream:
        return json.load(stream)


def _load_g4setup(selector):
    path = component_path(
        "g4setup",
        str(selector) + ".json",
        roots=app_component_roots("cce"),
    )
    with path.open(encoding="utf-8") as stream:
        return path, json.load(stream)


def build_plan(kwargs) -> WorkflowPlan:
    defaults = load_defaults()
    g4setup = _load_g4setup(defaults["g4setup"])
    signal_plan = build_signal_plan(
        kwargs,
        g4setup=g4setup,
        workflow="cce",
        default_source=defaults["source"],
        default_afe=defaults["afe"],
    )
    adc_path, adc = load_component("adc", kwargs.get("adc") or defaults["adc"])
    components = signal_plan.components + (component_selection("ADC", adc_path, adc),)
    return WorkflowPlan(
        workflow="cce",
        device=signal_plan.device,
        field=signal_plan.field,
        components=components,
        stages=signal_plan.stages + ("ADC", "Metrics", "Charge-collection analysis"),
        output=signal_plan.output,
        work=signal_plan.work,
    )
