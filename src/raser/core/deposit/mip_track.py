"""Deposits of a toy MIP: a straight track with a fixed energy loss per um."""

from __future__ import annotations

import math

from raser.core.seeding import stream

from .deposits import Deposits, EventDeposits
from .generation import GENERATED_LIMIT
from .generation import generation
from .ionization import PAIR_ENERGY_EV

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
    my_d,
    source: dict,
    events: int | None,
    max_step: float,
    edep_min: float | None = None,
    edep_max: float | None = None,
    generated: int | None = None,
    generated_limit: int = GENERATED_LIMIT,
) -> Deposits:
    """Deposits of straight tracks through the device: `events` recorded
    ones, generated until there are that many, or those recorded of
    `generated` tracks; one of the two is None. More than generated_limit
    tracks for the `events` asked for is an error.

    Keys of source:
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
    and the slope. All deposits of a track are at time 0. Events whose
    total energy [MeV] lies outside edep_min, edep_max are not recorded.
    """
    unknown = sorted(set(source) - _SOURCE_KEYS)
    if unknown:
        raise ValueError(
            f"keys {unknown} of the toy MIP source are not read; "
            f"known: {sorted(_SOURCE_KEYS)}"
        )
    if "landau_sampling" not in source:
        raise ValueError("the toy MIP source must say landau_sampling: true or false")
    material = my_d.material
    if material not in PAIRS_PER_UM:
        raise ValueError(
            f"no toy MIP energy loss for the material {material!r}; "
            f"known: {sorted(PAIRS_PER_UM)}"
        )
    energy_per_um = PAIRS_PER_UM[material] * PAIR_ENERGY_EV[material] * 1.0e-6
    width_per_um = LANDAU_WIDTH_MEV_PER_UM[material]
    generator = stream("toy_mip")

    recorded: list[EventDeposits] = []
    number = -1
    for number in generation(events, generated, generated_limit, lambda: len(recorded)):
        start, end = _track_ends(my_d, source, generator)
        length = math.dist(start, end)
        if "packets" in source:
            count = int(source["packets"])
        else:
            count = math.ceil(length / max_step)
        piece = length / count
        energies = []
        for _ in range(count):
            if source["landau_sampling"]:
                energy = generator.Landau(energy_per_um * piece, width_per_um * piece)
                energies.append(max(0.0, energy))
            else:
                energies.append(energy_per_um * piece)
        total = sum(energies)
        if edep_min is not None and total < edep_min:
            continue
        if edep_max is not None and total > edep_max:
            continue
        fractions = [(k + 0.5) / count for k in range(count)]
        x, y, z = (
            [start[axis] + f * (end[axis] - start[axis]) for f in fractions]
            for axis in range(3)
        )
        recorded.append(
            EventDeposits(number, ["Device"] * count, x, y, z, [0.0] * count, energies)
        )
    return Deposits(number + 1, edep_min, edep_max, recorded)


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
