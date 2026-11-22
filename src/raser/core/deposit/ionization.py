"""Electron-hole pairs created by the energy deposits of one event."""

from __future__ import annotations

import math
from collections.abc import Mapping

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
    event: EventDeposits, material: str | Mapping[str, str], fano: bool = True
) -> tuple[list[float], list[list[float]]]:
    """Number of pairs of every deposit and where and when they appear.

    material is the material of the deposits of the event, or, for deposits
    in several detectors, the material of each detector by its name; a
    deposit takes the material of the detector it lies in.

    With fano, the number is drawn around the mean E / pair energy with the
    variance Fano factor * mean, from the stream of this event number; without, it is the mean itself, and the
    material needs no Fano factor. The second list holds [x, y, z, t] of
    every deposit: position [um] in the coordinates of the detector and
    time [s].
    """
    materials = (
        [material] * len(event.e)
        if isinstance(material, str)
        else [material[name] for name in event.detector]
    )
    for one in set(materials):
        if one not in PAIR_ENERGY_EV:
            raise ValueError(
                f"no pair energy for the material {one!r}; known: {sorted(PAIR_ENERGY_EV)}"
            )
    if not fano:
        pairs = [
            energy / (PAIR_ENERGY_EV[one] * 1.0e-6)
            for energy, one in zip(event.e, materials)
        ]
        positions = [list(point) for point in zip(event.x, event.y, event.z, event.t)]
        return pairs, positions
    for one in set(materials):
        if one not in FANO_FACTOR:
            raise ValueError(
                f"no Fano factor for the material {one!r}; known: {sorted(FANO_FACTOR)}"
            )
    # each event draws from its own stream: the pairs of an event do not
    # depend on which other events were recorded before it
    generator = stream(f"ionization/{event.event}")
    pairs = []
    for energy, one in zip(event.e, materials):
        mean = energy / (PAIR_ENERGY_EV[one] * 1.0e-6)
        sigma = math.sqrt(FANO_FACTOR[one] * mean)
        pairs.append(max(0.0, generator.Gaus(mean, sigma)))
    positions = [list(point) for point in zip(event.x, event.y, event.z, event.t)]
    return pairs, positions
