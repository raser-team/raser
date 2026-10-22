"""Runtime construction shared by Signal entry points."""

from copy import deepcopy

from raser.apps._planning import ComponentSelection
from raser.apps._planning import WorkflowPlan

from raser.core.current import cal_current as current
from raser.core.interaction.toy_mip import ToyMIPInteraction


DEVICE_G4_CONFIG = {
    "geant4_model": "device",
    "total_events": 1,
    "object": {},
    "world": "G4_Galactic",
    "maxstep": 2,
    "g4_vis": False,
}


def _component(
    plan: WorkflowPlan,
    kind: str,
    *,
    required: bool = True,
) -> ComponentSelection | None:
    matches = [component for component in plan.components if component.kind == kind]
    if len(matches) == 1:
        return matches[0]
    if not matches and not required:
        return None
    raise ValueError(f"{plan.workflow} requires one {kind} component")


def apply_signal_plan(detector, kwargs):
    plan = kwargs.get("_workflow_plan")
    if not isinstance(plan, WorkflowPlan):
        raise RuntimeError("Signal requires an activated workflow plan")

    source = _component(plan, "Source")
    afe = _component(plan, "AFE")
    g4setup = _component(plan, "G4Setup", required=False)
    adc = _component(plan, "ADC", required=False)
    assert source is not None
    assert afe is not None

    g4_config = deepcopy(
        dict(g4setup.values) if g4setup is not None else DEVICE_G4_CONFIG
    )
    g4_config.update(source.values)
    if "kind" in source.values:
        g4_config["source_kind"] = source.values["kind"]
    for metadata_key in ("name", "kind", "description"):
        g4_config.pop(metadata_key, None)

    detector.g4experiment = g4setup.name if g4setup is not None else "device"
    detector.g4_config = g4_config
    detector.amplifier = afe.name
    if adc is not None:
        detector.daq = adc.name
    detector.signal_source = source.name
    detector.signal_output_label = plan.workflow
    return plan


def build_interaction(detector, seed, g4_vis, **options):
    if detector.g4_config.get("source_kind") == "toy_mip":
        return ToyMIPInteraction(detector, detector.g4_config, seed)

    from raser.core.interaction.interaction import GeneralG4Interaction

    return GeneralG4Interaction(
        detector,
        detector.g4_config,
        seed,
        g4_vis,
        **options,
    )


def is_toy_mip_source(interaction):
    return getattr(interaction, "geant4_model", None) == "toy_mip"


def build_current(detector, field, interaction, batch, *, keep_drift_paths=True):
    if is_toy_mip_source(interaction):
        return current.CalCurrentToyMIP(
            detector,
            field,
            interaction.source(batch),
            keep_drift_paths=keep_drift_paths,
        )
    return current.CalCurrentG4P(
        detector,
        field,
        interaction,
        batch,
        keep_drift_paths=keep_drift_paths,
    )
