"""The entry of the energy-deposition stage: one job in, its Deposits out."""

from __future__ import annotations

import copy

from .deposits import Deposits
from .mip_track import mip_deposits

# Kinds of source that Geant4 simulates.
G4_KINDS = ("beam", "decay_source")

# Without a g4setup the device stands alone in vacuum.
DEVICE_ALONE = {
    "geant4_model": "device",
    "object": {},
    "world": "G4_Galactic",
    "maxstep": 2,
    "g4_vis": False,
}

_DESCRIPTIVE_KEYS = ("name", "kind", "description")


def g4_configuration(
    source: dict,
    g4setup: dict | None,
    events: int,
    edep_min: float | None,
    edep_max: float | None,
) -> dict:
    """The configuration Geant4 runs with.

    The g4setup gives the surroundings and the step limit, the source the
    particle; the number of events and the window of the energy deposited
    in the device [MeV] are of the experiment and replace whatever the two
    files say.
    """
    configuration = copy.deepcopy(DEVICE_ALONE if g4setup is None else g4setup)
    configuration.update(copy.deepcopy(source))
    for key in _DESCRIPTIVE_KEYS:
        configuration.pop(key, None)
    configuration["total_events"] = int(events)
    configuration["edep_min"] = edep_min
    configuration["edep_max"] = edep_max
    return configuration


def simulate_deposits(
    my_d,
    source: dict,
    g4setup: dict | None,
    events: int,
    g4_seed: int,
    edep_min: float | None = None,
    edep_max: float | None = None,
) -> Deposits:
    """Deposits of `events` generated events of `source` in the device.

    source and g4setup are the contents of the component files; g4setup
    None is the device alone in vacuum. edep_min and edep_max [MeV] bound
    the energy deposited in the device; events outside are not recorded.
    A toy MIP takes only the step limit from the g4setup and does not use
    g4_seed.
    """
    kind = source.get("kind")
    if kind == "toy_mip":
        max_step = (DEVICE_ALONE if g4setup is None else g4setup)["maxstep"]
        return mip_deposits(my_d, source, events, max_step, edep_min, edep_max)
    if kind not in G4_KINDS:
        raise ValueError(
            f"no simulation of deposits for a source of kind {kind!r}; "
            f"known: {['toy_mip', *G4_KINDS]}"
        )
    # g4ppyy creates the Geant4 managers when imported; sources that do
    # not need Geant4 must not pay for it.
    from .interaction import GeneralG4Interaction

    my_g4 = GeneralG4Interaction(
        my_d, g4_configuration(source, g4setup, events, edep_min, edep_max), g4_seed
    )
    try:
        return my_g4.deposits()
    finally:
        my_g4.close()
