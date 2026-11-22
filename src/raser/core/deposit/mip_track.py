"""Deposits of a toy MIP: a straight track with a fixed energy loss per um."""

from __future__ import annotations

import math

from raser.core.seeding import stream

from .deposits import Deposits, EventDeposits
from .along_beam import Layout
from .generation import GENERATED_LIMIT
from .generation import generation
from .ionization import PAIR_ENERGY_EV
from .recording import event_recorded, parse_require

# Electron-hole pairs a MIP creates per um of track.
PAIRS_PER_UM = {"Si": 80.0, "SiC": 55.0}
# Width of the Landau fluctuation of the energy loss [MeV/um].
LANDAU_WIDTH_MEV_PER_UM = {"Si": 2.0e-5, "SiC": 3.2e-5}

_SOURCE_KEYS = {
    "name",
    "kind",
    "description",
    "start",
    "end",
    "position_range_um",
    "direction_sigma_mrad",
    "packets",
    "landau_sampling",
}


def mip_deposits(
    devices,
    layout: Layout,
    source: dict,
    events: int | None,
    max_step: float,
    windows,
    require: str,
    coincidence_window_ns: float | None,
    generated: int | None = None,
    generated_limit: int = GENERATED_LIMIT,
) -> Deposits:
    """Deposits of straight tracks through the devices: `events` recorded
    ones, generated until there are that many, or those recorded of
    `generated` tracks; one of the two is None. More than generated_limit
    tracks for the `events` asked for is an error.

    With one slot, the track runs in the coordinates of its device. Keys of
    source:
        landau_sampling       whether the energy of each deposit fluctuates
        start, end            ends of the track [um]; without them the track
                              goes through the centre from z = 0 to z = l_z
        position_range_um     {"x": [lo, hi], "y": [lo, hi]}: the start is
                              drawn uniformly in it
        direction_sigma_mrad  {"x": sigma, "y": sigma}: the slopes dx/dz and
                              dy/dz are drawn around 0
        packets               number of deposits of a track; without it the
                              track is cut into pieces no longer than
                              max_step [um]
    With a position range or a drawn slope the end follows from the start
    and the slope.

    With more than one slot, the track starts at the source, the origin of
    the Geant4 world of `layout`, and runs along +z with the slopes drawn
    around 0 (direction_sigma_mrad); start, end and position_range_um are
    errors. In each slot it is the part of the track in the active layer,
    cut as above, and the pieces whose middle lies outside the device across
    x and y (outside [0, l_x] x [0, l_y]) are left out.

    All deposits of a track are at time 0. An event is recorded when the
    slots hit (the energy [MeV] of the pieces of the slot above 0 and in its
    window) satisfy `require` (see raser.core.deposit.recording); every slot
    keeps its pieces.
    """
    unknown = sorted(set(source) - _SOURCE_KEYS)
    if unknown:
        raise ValueError(
            f"keys {unknown} of the toy MIP source are not read; "
            f"known: {sorted(_SOURCE_KEYS)}"
        )
    if "landau_sampling" not in source:
        raise ValueError("the toy MIP source must say landau_sampling: true or false")
    slots = list(devices)
    for slot in slots:
        material = devices[slot].material
        if material not in PAIRS_PER_UM:
            raise ValueError(
                f"no toy MIP energy loss for the material {material!r}; "
                f"known: {sorted(PAIRS_PER_UM)}"
            )
    multi = len(slots) > 1
    if multi:
        given = sorted({"start", "end", "position_range_um"} & set(source))
        if given:
            raise ValueError(
                f"keys {given} of the toy MIP source are not read with more than one slot: "
                "the track starts at the source of the g4setup"
            )
    tree = parse_require(require, slots)
    generator = stream("toy_mip")

    recorded: list[EventDeposits] = []
    number = -1
    for number in generation(events, generated, generated_limit, lambda: len(recorded)):
        if multi:
            record = _multi_slot_event(
                number, devices, layout, source, generator, max_step, windows, tree,
                coincidence_window_ns,
            )
        else:
            record = _single_slot_event(
                number, slots[0], devices[slots[0]], source, generator, max_step, windows,
                tree, coincidence_window_ns,
            )
        if record is not None:
            recorded.append(record)
    return Deposits(number + 1, dict(windows), require, coincidence_window_ns, recorded)


def _energies(material, source, generator, count, piece):
    """The energies [MeV] of `count` pieces of a track, each `piece` [um] long."""
    energy_per_um = PAIRS_PER_UM[material] * PAIR_ENERGY_EV[material] * 1.0e-6
    width_per_um = LANDAU_WIDTH_MEV_PER_UM[material]
    energies = []
    for _ in range(count):
        if source["landau_sampling"]:
            energy = generator.Landau(energy_per_um * piece, width_per_um * piece)
            energies.append(max(0.0, energy))
        else:
            energies.append(energy_per_um * piece)
    return energies


def _count(source, length, max_step):
    if "packets" in source:
        return int(source["packets"])
    return math.ceil(length / max_step)


def _single_slot_event(
    number, slot, my_d, source, generator, max_step, windows, tree, coincidence_window_ns
):
    start, end = _track_ends(my_d, source, generator)
    length = math.dist(start, end)
    count = _count(source, length, max_step)
    piece = length / count
    energies = _energies(my_d.material, source, generator, count, piece)
    if not event_recorded(
        tree, [slot], windows, {slot: sum(energies)}, {slot: 0.0}, coincidence_window_ns
    ):
        return None
    fractions = [(k + 0.5) / count for k in range(count)]
    x, y, z = (
        [start[axis] + f * (end[axis] - start[axis]) for f in fractions] for axis in range(3)
    )
    # each piece starts where the one before it ends
    x_start, y_start, z_start = (
        [start[axis] + k / count * (end[axis] - start[axis]) for k in range(count)]
        for axis in range(3)
    )
    return EventDeposits(
        number, [slot] * count, x, y, z, [0.0] * count, energies,
        x_start=x_start, y_start=y_start, z_start=z_start,
    )


def _multi_slot_event(
    number, devices, layout, source, generator, max_step, windows, tree, coincidence_window_ns
):
    slopes = _slopes(source, generator)
    along = math.sqrt(1.0 + slopes[0] ** 2 + slopes[1] ** 2)
    detector: list[str] = []
    columns: dict[str, list[float]] = {name: [] for name in ("x", "y", "z", "t", "e")}
    starts: dict[str, list[float]] = {name: [] for name in ("x", "y", "z")}
    energies, first_times = {}, {}
    for slot, my_d in devices.items():
        placed = layout.slot(slot)
        z_front, z_back = placed.active_z
        length = (z_back - z_front) * along
        count = _count(source, length, max_step)
        piece = length / count
        slot_energies = _energies(my_d.material, source, generator, count, piece)
        kept = []
        for k, energy in enumerate(slot_energies):
            middle = placed.to_device(
                *_point_on_track(slopes, z_front + (k + 0.5) / count * (z_back - z_front))
            )
            if not (0 <= middle[0] <= placed.l_x and 0 <= middle[1] <= placed.l_y):
                continue
            begin = placed.to_device(
                *_point_on_track(slopes, z_front + k / count * (z_back - z_front))
            )
            kept.append((middle, begin, energy))
        energies[slot] = sum(energy for _, _, energy in kept)
        first_times[slot] = 0.0
        for middle, begin, energy in kept:
            detector.append(slot)
            for axis, name in enumerate(("x", "y", "z")):
                columns[name].append(middle[axis])
                starts[name].append(begin[axis])
            columns["t"].append(0.0)
            columns["e"].append(energy)
    if not event_recorded(
        tree, list(devices), windows, energies, first_times, coincidence_window_ns
    ):
        return None
    return EventDeposits(
        number, detector, columns["x"], columns["y"], columns["z"], columns["t"], columns["e"],
        x_start=starts["x"], y_start=starts["y"], z_start=starts["z"],
    )


def _point_on_track(slopes, z):
    return (slopes[0] * z, slopes[1] * z, z)


def _slopes(source: dict, generator) -> list[float]:
    """The slopes dx/dz and dy/dz of a track, drawn around 0 as the
    direction_sigma_mrad of the source says."""
    slopes = [0.0, 0.0]
    if "direction_sigma_mrad" in source:
        for axis, name in enumerate(("x", "y")):
            sigma = source["direction_sigma_mrad"][name] * 1.0e-3
            if sigma > 0:
                slopes[axis] = generator.Gaus(0.0, sigma)
    return slopes


def _track_ends(my_d, source: dict, generator) -> tuple[list[float], list[float]]:
    start = [float(v) for v in source.get("start", [my_d.l_x / 2, my_d.l_y / 2, 0.0])]
    end = [float(v) for v in source.get("end", [my_d.l_x / 2, my_d.l_y / 2, my_d.l_z])]
    drawn = False
    if "position_range_um" in source:
        start[0] = generator.Uniform(*source["position_range_um"]["x"])
        start[1] = generator.Uniform(*source["position_range_um"]["y"])
        drawn = True
    slopes = [0.0, 0.0]
    if "direction_sigma_mrad" in source:
        for axis, name in enumerate(("x", "y")):
            sigma = source["direction_sigma_mrad"][name] * 1.0e-3
            if sigma > 0:
                slopes[axis] = generator.Gaus(0.0, sigma)
                drawn = True
    if drawn:
        end[0] = start[0] + slopes[0] * (end[2] - start[2])
        end[1] = start[1] + slopes[1] * (end[2] - start[2])
    return start, end
