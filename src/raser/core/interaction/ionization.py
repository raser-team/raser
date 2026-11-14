"""Electron-hole pairs created by the energy deposits of one event."""

from __future__ import annotations

import math

from raser.core.seeding import stream

from .deposits import EventDeposits

# Mean energy to create one electron-hole pair [eV].
PAIR_ENERGY_EV = {"Si": 3.6, "SiC": 8.4}
# Variance of the number of pairs over its mean.
FANO_FACTOR = {"Si": 0.115, "SiC": 0.128}


def ionized_pairs(
    event: EventDeposits, material: str
) -> tuple[list[float], list[list[float]]]:
    """Number of pairs of every deposit and where and when they appear.

    The number is drawn around the mean E / pair energy with the variance
    Fano factor * mean. The second list holds [x, y, z, t] of every
    deposit: position [um] in the coordinates of the detector and time [s].
    """
    if material not in PAIR_ENERGY_EV:
        raise ValueError(
            f"no pair energy and Fano factor for the material {material!r}; "
            f"known: {sorted(PAIR_ENERGY_EV)}"
        )
    pair_energy_mev = PAIR_ENERGY_EV[material] * 1.0e-6
    fano_factor = FANO_FACTOR[material]
    generator = stream("ionization")
    pairs = []
    for energy in event.e:
        mean = energy / pair_energy_mev
        sigma = math.sqrt(fano_factor * mean)
        pairs.append(max(0.0, generator.Gaus(mean, sigma)))
    positions = [list(point) for point in zip(event.x, event.y, event.z, event.t)]
    return pairs, positions
