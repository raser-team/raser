"""Runtime construction shared by Signal entry points."""

from copy import deepcopy
from pathlib import Path

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


def component_name(kwargs, kind, option):
    """Name of a component: the one in its file, else the file it was read from."""
    return str(kwargs["_files"][kind].get("name") or Path(str(kwargs[option])).stem)


def apply_signal_plan(detector, kwargs):
    """Hang the component names of the run on the detector and return the
    Geant4 configuration built from its component files."""
    state = kwargs["_files"]
    g4_config = deepcopy(state.get("g4setup", DEVICE_G4_CONFIG))
    g4_config.update(state["source"])
    if "kind" in state["source"]:
        g4_config["source_kind"] = state["source"]["kind"]
    for metadata_key in ("name", "kind", "description"):
        g4_config.pop(metadata_key, None)

    detector.g4experiment = "device"
    if "g4setup" in state:
        detector.g4experiment = component_name(kwargs, "g4setup", "g4setup")
    detector.amplifier = component_name(kwargs, "afe", "amplifier")
    if "adc" in state:
        detector.daq = component_name(kwargs, "adc", "adc")
    detector.signal_source = component_name(kwargs, "source", "source")
    detector.signal_output_label = kwargs["_signal_label"]
    return g4_config


def build_interaction(detector, g4_config, seed, g4_vis, **options):
    if g4_config.get("source_kind") == "toy_mip":
        return ToyMIPInteraction(detector, g4_config)

    from raser.core.interaction.interaction import GeneralG4Interaction

    return GeneralG4Interaction(
        detector,
        g4_config,
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
