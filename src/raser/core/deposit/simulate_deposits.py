"""The energy-deposition stage: the Deposits of one job, and their file."""

from __future__ import annotations

import copy
import math

from .deposits import Deposits
from .deposits import write_deposits
from .ionization import ionized_pairs
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

# Half the side of the Geant4 world [um] when nothing reaches farther.
WORLD_HALF_SIDE = 25000

_DESCRIPTIVE_KEYS = ("name", "kind", "description")
_PARTICLE_KEYS = ("par_in", "par_out", "par_randx", "par_randy", "par_type", "par_energy")


def g4_configuration(
    source: dict,
    g4setup: dict | None,
    events: int,
    edep_min: float | None,
    edep_max: float | None,
) -> dict:
    """The configuration Geant4 runs with.

    The g4setup gives the surroundings and the step limit, the source the
    particle. A source with "particles" fires all of them in every event:
    each takes from the source what it does not give itself (par_in, par_out,
    par_randx, par_randy, par_type, par_energy).
    The number of events and the window of the energy deposited
    in the device [MeV] are of the experiment and replace whatever the two
    files say.
    """
    configuration = copy.deepcopy(DEVICE_ALONE if g4setup is None else g4setup)
    configuration.update(copy.deepcopy(source))
    for key in _DESCRIPTIVE_KEYS:
        configuration.pop(key, None)
    if "particles" in configuration:
        configuration["particles"] = [
            {**{key: configuration[key] for key in _PARTICLE_KEYS if key in configuration}, **one}
            for one in configuration["particles"]
        ]
    configuration["total_events"] = int(events)
    configuration["edep_min"] = edep_min
    configuration["edep_max"] = edep_max
    return configuration


def generated_fraction(source: dict) -> float:
    """The part of what the source emits that is generated: of a source of
    nuclides with par_cone [degree], the directions within the cone."""
    if "nuclides" in source and source.get("par_cone") is not None:
        return (1 - math.cos(math.radians(source["par_cone"]))) / 2
    return 1.0


def world_half_side(my_d, configuration: dict) -> float:
    """Half the side [um] of the cube of the Geant4 world, centred where
    the device's face z = 0 has its middle.

    It is WORLD_HALF_SIDE, unless the device, an object of the
    configuration or a point the source starts from (par_in, of every
    particle, widened by par_radius) reaches farther along x, y or z: then
    it is twice that reach, so that the world holds them with room around.
    """
    reach = max(my_d.l_x / 2, my_d.l_y / 2, my_d.l_z)
    for objects in (configuration.get("object") or {}).values():
        for one in objects.values():
            reach = max(
                reach,
                *(abs(one["position_" + axis]) + one["side_" + axis] / 2 for axis in "xyz"),
            )
    radius = configuration.get("par_radius", 0)
    for one in (configuration, *configuration.get("particles", ())):
        if "par_in" in one:
            reach = max(reach, *(abs(c) + radius for c in one["par_in"]))
    return WORLD_HALF_SIDE if reach <= WORLD_HALF_SIDE else 2 * reach


def tilted(source: dict, l_z: float) -> dict:
    """`source` turned by its par_angle [degree], the angle of incidence.

    The points par_in and par_out [um] of the source, and those of its
    "particles", are turned by par_angle about the axis along y through the
    point where the line from par_in to par_out enters the device, on its
    face z = 0 or z = l_z. The particles keep hitting that point, and a source
    just off the face stays outside the device. A source along -z comes, at a
    positive angle, with a component along -x. The spread par_randx and
    par_randy stays along x and y; the g4setup does not move.
    """
    angle = source.get("par_angle")
    if not angle:
        return source
    if "par_in" not in source or "par_out" not in source:
        raise ValueError(
            f"a source of kind {source.get('kind')!r} has no par_in and par_out "
            f"to turn by par_angle = {angle}"
        )
    (x0, _, z0), (x1, _, z1) = source["par_in"], source["par_out"]
    if 0 <= z0 <= l_z or z1 == z0:
        raise ValueError(
            f"the source runs from z = {z0} um to z = {z1} um and enters neither "
            f"face of the device (z = 0 and z = {l_z} um): there is no point to "
            f"turn it about by par_angle = {angle}"
        )
    face = l_z if z0 > l_z else 0.0
    pivot_x = x0 + (face - z0) / (z1 - z0) * (x1 - x0)
    cos, sin = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    turned = copy.deepcopy(source)
    for one in (turned, *turned.get("particles", ())):
        for key in ("par_in", "par_out"):
            if key in one:
                x, y, z = one[key]
                x, z = x - pivot_x, z - face
                one[key] = [x * cos + z * sin + pivot_x, y, -x * sin + z * cos + face]
    return turned


def simulate_deposits(
    my_d,
    source: dict,
    g4setup: dict | None,
    events: int,
    g4_seed: int,
    edep_min: float | None = None,
    edep_max: float | None = None,
    fano: bool = True,
) -> Deposits:
    """Deposits of `events` generated events of `source` in the device,
    each with the electron-hole pairs it created in the material of the device.

    source and g4setup are the contents of the component files; g4setup
    None is the device alone in vacuum. edep_min and edep_max [MeV] bound
    the energy deposited in the device; events outside are not recorded.
    fano draws the number of pairs of each deposit with the Fano variance;
    without, it is energy / pair energy.
    A toy MIP takes only the step limit from the g4setup and does not use
    g4_seed. The source comes at its par_angle [degree], see `tilted`.
    """
    deposits = _energy_deposits(my_d, source, g4setup, events, g4_seed, edep_min, edep_max)
    deposits.generated_fraction = generated_fraction(source)
    for event in deposits.events:
        event.pairs, _ = ionized_pairs(event, my_d.material, fano)
    return deposits


def _energy_deposits(my_d, source, g4setup, events, g4_seed, edep_min, edep_max) -> Deposits:
    kind = source.get("kind")
    if kind != "toy_mip" and kind not in G4_KINDS:
        raise ValueError(
            f"no simulation of deposits for a source of kind {kind!r}; "
            f"known: {['toy_mip', *G4_KINDS]}"
        )
    source = tilted(source, my_d.l_z)
    if kind == "toy_mip":
        max_step = (DEVICE_ALONE if g4setup is None else g4setup)["maxstep"]
        return mip_deposits(my_d, source, None, max_step, edep_min, edep_max, generated=events)
    # g4ppyy creates the Geant4 managers when imported; sources that do
    # not need Geant4 must not pay for it.
    from .geant4.interaction import GeneralG4Interaction

    my_g4 = GeneralG4Interaction(
        my_d, g4_configuration(source, g4setup, events, edep_min, edep_max), g4_seed
    )
    try:
        return my_g4.deposits()
    finally:
        my_g4.close()


def write_simulated_deposits(
    deposits_path,
    my_d,
    source: dict,
    g4setup: dict | None,
    events: int,
    g4_seed: int,
    edep_min: float | None = None,
    edep_max: float | None = None,
    fano: bool = True,
) -> int:
    """simulate_deposits, written to the deposits file; a file an earlier
    start left there is replaced. Returns the number of recorded events."""
    deposits = simulate_deposits(
        my_d, source, g4setup, events, g4_seed, edep_min, edep_max, fano
    )
    write_deposits(deposits_path, deposits)
    return len(deposits.events)
