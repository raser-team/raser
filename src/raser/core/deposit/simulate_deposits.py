"""The energy-deposition stage: the Deposits of one job, and their file."""

from __future__ import annotations

import copy
import math
from collections.abc import Mapping
from typing import Any

from .along_beam import SLOT_COLOUR, Layout, PlacedSlot, parse_along_beam
from .deposits import Deposits
from .deposits import write_deposits
from .generation import GENERATED_LIMIT
from .generation import asked
from .ionization import ionized_pairs
from .mip_track import mip_deposits
from .recording import check_condition

# Kinds of source that Geant4 simulates.
G4_KINDS = ("beam", "decay_source")

# Without a g4setup the device stands alone in vacuum, the source 17 mm
# in front of its front face and aimed at the middle of it.
DEVICE_ALONE: dict[str, Any] = {
    "geant4_model": "device",
    "object": {},
    "world": "G4_Galactic",
    "maxstep": 2,
    "g4_vis": False,
    "source": {"angle": 0},
    "along_beam": ["source", {"gap": 17000}, {"slot": "Device"}],
}

# Half the side of the Geant4 world [um] when nothing reaches farther.
WORLD_HALF_SIDE = 25000

_DESCRIPTIVE_KEYS = ("name", "kind", "description")
_PARTICLE_KEYS = ("par_in", "par_out", "par_randx", "par_randy", "par_type", "par_energy")
# Where a source sits and where it aims belong to the g4setup.
_PLACEMENT_KEYS = ("par_in", "par_out", "par_angle")


def layout_of(devices: Mapping, g4setup: dict | None) -> Layout:
    """Where the slots and objects of the g4setup lie in the Geant4 world
    (`parse_along_beam`), for the devices of its slots. A g4setup that
    imports a GDML file has no along_beam: its one slot, "Device", has the
    face z = 0 of its device at the origin, facing the source."""
    setup = DEVICE_ALONE if g4setup is None else g4setup
    if setup.get("geant4_model") != "gdml_import":
        return parse_along_beam(setup, devices)
    if list(devices) != ["Device"]:
        raise ValueError(
            f"the g4setup places ['Device'], the devices are {list(devices)}"
        )
    my_d = devices["Device"]
    return Layout(
        (),
        (
            PlacedSlot(
                "Device", 0.0, (0.0, 0.0), "upstream", 0, SLOT_COLOUR,
                float(my_d.l_x), float(my_d.l_y), float(my_d.l_z), 0.0,
            ),
        ),
        0.0,
    )


def g4_configuration(
    source: dict,
    g4setup: dict | None,
    layout: Layout,
    events: int | None,
    windows: Mapping,
    require: str,
    coincidence_window_ns: float | None,
    generated: int | None = None,
    generated_limit: int = GENERATED_LIMIT,
) -> dict:
    """The configuration Geant4 runs with, in the coordinates of Geant4: the
    origin is on the source and z runs along the beam (`layout`).

    The g4setup gives the surroundings, the step limit and the column along
    the beam; its key "source" = {"angle"} [degree] turns the source by the
    angle of incidence (see `tilted`). The source sits at the origin and aims
    along +z at the point of the first slot where its front face is: par_in
    and par_out of the configuration. The source gives what it emits, and no
    place or direction. A source with "particles" fires all of them in
    every event: each takes from the source what it does not give itself
    (par_randx, par_randy, par_type, par_energy) and is moved by its "offset"
    [um]. The events and the conditions on the energy deposited in the
    slots (`windows` [MeV], require, coincidence_window_ns) are of the
    experiment and replace whatever the two files say: recorded_events is
    `events`, None when `generated` events are asked for; total_events is
    the events to generate, `generated` or at most generated_limit.
    """
    asked(events, generated, generated_limit)
    placed = sorted(
        {key for one in (source, *source.get("particles", ())) for key in one}
        & set(_PLACEMENT_KEYS)
    )
    if placed:
        raise ValueError(
            f"the source {source.get('name')!r} gives {placed}: where a source sits "
            "and where it aims are of the g4setup, in its along_beam and source = {angle}"
        )
    configuration = copy.deepcopy(DEVICE_ALONE if g4setup is None else g4setup)
    placement: dict = configuration.pop("source", {})
    configuration.pop("along_beam", None)
    configuration.update(copy.deepcopy(source))
    for key in _DESCRIPTIVE_KEYS:
        configuration.pop(key, None)
    if configuration.get("geant4_model") == "gdml_import":
        # the GDML file holds the surroundings; the g4setup says where the source is
        if "at" not in placement or "towards" not in placement:
            raise ValueError(
                f"the g4setup {(g4setup or {}).get('name')!r} does not place the source: "
                "give it source = {at, towards, angle}"
            )
        configuration["par_in"] = [float(c) for c in placement["at"]]
        configuration["par_out"] = [float(c) for c in placement["towards"]]
    else:
        front = layout.slots[0].z
        if front <= 0:
            raise ValueError(
                f"the first slot {layout.slots[0].name!r} of the g4setup is at z = {front} um: "
                "the source has no direction to the face of the first slot"
            )
        configuration["par_in"] = [0.0, 0.0, 0.0]
        configuration["par_out"] = [0.0, 0.0, float(front)]
    configuration["par_angle"] = placement.get("angle", 0)
    if "particles" in configuration:
        particles = []
        for one in configuration["particles"]:
            one = dict(one)
            offset = one.pop("offset", [0, 0, 0])
            particles.append(
                {
                    **{key: configuration[key] for key in _PARTICLE_KEYS if key in configuration},
                    **one,
                    "par_in": [a + b for a, b in zip(configuration["par_in"], offset)],
                    "par_out": [a + b for a, b in zip(configuration["par_out"], offset)],
                }
            )
        configuration["particles"] = particles
    configuration["recorded_events"] = None if events is None else int(events)
    configuration["total_events"] = int(generated_limit if generated is None else generated)
    configuration["windows"] = dict(windows)
    configuration["require"] = require
    configuration["coincidence_window_ns"] = coincidence_window_ns
    return configuration


def generated_fraction(source: dict) -> float:
    """The part of what the source emits that is generated: of a source of
    nuclides with par_cone [degree], the directions within the cone."""
    if "nuclides" in source and source.get("par_cone") is not None:
        return (1 - math.cos(math.radians(source["par_cone"]))) / 2
    return 1.0


def world_half_side(layout: Layout, configuration: dict) -> float:
    """Half the side [um] of the cube of the Geant4 world, which Geant4
    centres on the origin, the source.

    A cube centred on the middle of the column along the beam has half the
    side WORLD_HALF_SIDE, unless half the length of the column, the reach of
    an item of it across the axis (the offset of its centre and half its
    width along x or y) or the radius of the source disk par_radius reaches
    farther: then it is twice that reach, so that it holds them with room
    around. The world is the cube about the origin that holds that one, so
    half the length of the column is added to its half side.
    """
    reach = max(layout.length / 2, layout.reach, configuration.get("par_radius", 0))
    half = WORLD_HALF_SIDE if reach <= WORLD_HALF_SIDE else 2 * reach
    return half + layout.length / 2


def tilted(source: dict, layout: Layout) -> dict:
    """The configuration `source` turned by its par_angle [degree], the
    angle of incidence.

    The points par_in and par_out [um] of the source, and those of its
    "particles", are turned by par_angle about the axis along y through the
    middle of the front face of the one slot, (P_x, P_y, P_z): the particles
    keep hitting that point. A source along +z comes, at a positive angle,
    with a component along +x, from the -x side. The spread par_randx and
    par_randy stays along x and y; the slots and objects do not move. A
    g4setup with more than one slot tilts no source (ValueError).
    """
    angle = source.get("par_angle")
    if not angle:
        return source
    if len(layout.slots) != 1:
        raise ValueError("a multi-slot g4setup tilts no source")
    slot = layout.slots[0]
    if "par_in" not in source or "par_out" not in source:
        raise ValueError(
            f"a source of kind {source.get('kind')!r} has no par_in and par_out "
            f"to turn by par_angle = {angle}"
        )
    (_, _, z0), (_, _, z1) = source["par_in"], source["par_out"]
    pivot_x, pivot_y, face = slot.front
    if slot.z <= z0 <= slot.z + slot.thickness or z1 == z0:
        raise ValueError(
            f"the source runs from z = {z0} um to z = {z1} um and enters neither "
            f"face of the slot {slot.name!r} (z = {slot.z} and z = {slot.z + slot.thickness} um): "
            f"there is no point to turn it about by par_angle = {angle}"
        )
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
    devices: Mapping,
    source: dict,
    g4setup: dict | None,
    events: int | None,
    g4_seed: int,
    windows: Mapping,
    require: str,
    coincidence_window_ns: float | None,
    fano: bool = True,
    generated: int | None = None,
    generated_limit: int = GENERATED_LIMIT,
    picture: str | None = None,
    drawn: int = 0,
) -> Deposits:
    """Deposits of `source` in the devices, each with the electron-hole pairs
    it created in the material of its device: `events` recorded events,
    generated until there are that many, or those recorded of `generated`
    events; one of the two is None. More than generated_limit events
    generated for the `events` asked for is an error.

    devices maps the name of each slot of the g4setup to its device, in the
    order of the deposits of an event. source and g4setup are the contents
    of the component files; g4setup None is the device alone in vacuum, in
    the slot "Device". windows maps each slot to the bounds (edep_min,
    edep_max) [MeV] of the energy deposited in it, None for a side that is
    not checked; an event is recorded when the logic expression `require`
    over the slots it hits holds, in the window coincidence_window_ns [ns]
    in time, None for any time (see raser.core.deposit.recording).
    fano draws the number of pairs of each deposit with the Fano variance;
    without, it is energy / pair energy.
    A toy MIP takes only the step limit from the g4setup and does not use
    g4_seed. The g4setup places the source, see `g4_configuration`.
    picture is the path, without its extension, of a png of the Geant4
    geometry and the first `drawn` recorded events, drawn during the run;
    a toy MIP draws none.
    """
    deposits = _energy_deposits(
        devices, source, g4setup, events, g4_seed, windows, require,
        coincidence_window_ns, generated, generated_limit, picture, drawn,
    )
    deposits.generated_fraction = generated_fraction(source)
    materials = {slot: my_d.material for slot, my_d in devices.items()}
    for event in deposits.events:
        event.pairs, _ = ionized_pairs(event, materials, fano)
    return deposits


def _energy_deposits(
    devices, source, g4setup, events, g4_seed, windows, require, coincidence_window_ns,
    generated, generated_limit, picture=None, drawn=0,
) -> Deposits:
    kind = source.get("kind")
    if kind != "toy_mip" and kind not in G4_KINDS:
        raise ValueError(
            f"no simulation of deposits for a source of kind {kind!r}; "
            f"known: {['toy_mip', *G4_KINDS]}"
        )
    asked(events, generated, generated_limit)
    layout = layout_of(devices, g4setup)
    check_condition(list(devices), windows, require, coincidence_window_ns)
    if kind == "toy_mip":
        max_step = float((DEVICE_ALONE if g4setup is None else g4setup)["maxstep"])
        return mip_deposits(
            devices, layout, source, events, max_step, windows, require,
            coincidence_window_ns, generated, generated_limit,
        )
    # g4ppyy creates the Geant4 managers when imported; sources that do
    # not need Geant4 must not pay for it.
    from .geant4.interaction import GeneralG4Interaction

    configuration = g4_configuration(
        source, g4setup, layout, events, windows, require, coincidence_window_ns,
        generated, generated_limit,
    )
    my_g4 = GeneralG4Interaction(
        devices, layout, tilted(configuration, layout), g4_seed, picture=picture, drawn=drawn
    )
    try:
        return my_g4.deposits()
    finally:
        my_g4.close()


def write_simulated_deposits(
    deposits_path,
    devices: Mapping,
    source: dict,
    g4setup: dict | None,
    events: int | None,
    g4_seed: int,
    windows: Mapping,
    require: str,
    coincidence_window_ns: float | None,
    fano: bool = True,
    generated: int | None = None,
    generated_limit: int = GENERATED_LIMIT,
    picture: str | None = None,
    drawn: int = 0,
) -> int:
    """simulate_deposits, written to the deposits file; a file an earlier
    start left there is replaced. Returns the number of recorded events."""
    deposits = simulate_deposits(
        devices, source, g4setup, events, g4_seed, windows, require, coincidence_window_ns,
        fano, generated, generated_limit, picture, drawn,
    )
    write_deposits(deposits_path, deposits)
    return len(deposits.events)
