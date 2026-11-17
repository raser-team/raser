"""Electron-hole pairs created by the energy deposits of one event."""

from __future__ import annotations

import math

from raser.core.seeding import stream

from .deposits import EventDeposits

# Mean energy to create one electron-hole pair [eV].
PAIR_ENERGY_EV = {
    "Si": 3.6,
    "SiC": 8.4,
    # T. Shimaoka et al., Phys. Status Solidi A 213 (2016) 2629,
    # doi:10.1002/pssa.201600195: CVD diamond, 5.486 MeV alpha of Am-241.
    "Diamond": 13.1,
}
# Variance of the number of pairs over its mean.
FANO_FACTOR = {
    "Si": 0.115,
    "SiC": 0.128,
    # Shimaoka et al. (above), measured: 0.382 +- 0.007.
    "Diamond": 0.382,
}


def ionized_pairs(
    event: EventDeposits, material: str, fano: bool = True
) -> tuple[list[float], list[list[float]]]:
    """Number of pairs of every deposit and where and when they appear.

    With fano, the number is drawn around the mean E / pair energy with the
    variance Fano factor * mean; without, it is the mean itself, and the
    material needs no Fano factor. The second list holds [x, y, z, t] of
    every deposit: position [um] in the coordinates of the detector and
    time [s].
    """
    if material not in PAIR_ENERGY_EV:
        raise ValueError(
            f"no pair energy for the material {material!r}; known: {sorted(PAIR_ENERGY_EV)}"
        )
    pair_energy_mev = PAIR_ENERGY_EV[material] * 1.0e-6
    if not fano:
        pairs = [energy / pair_energy_mev for energy in event.e]
        positions = [list(point) for point in zip(event.x, event.y, event.z, event.t)]
        return pairs, positions
    if material not in FANO_FACTOR:
        raise ValueError(
            f"no Fano factor for the material {material!r}; known: {sorted(FANO_FACTOR)}"
        )
    fano_factor = FANO_FACTOR[material]
    generator = stream("ionization")
    pairs = []
    for energy in event.e:
        mean = energy / pair_energy_mev
        sigma = math.sqrt(fano_factor * mean)
        pairs.append(max(0.0, generator.Gaus(mean, sigma)))
    positions = [list(point) for point in zip(event.x, event.y, event.z, event.t)]
    return pairs, positions
