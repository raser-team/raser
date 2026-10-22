"""Carrier creation data shared by particle and laser interactions."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Sequence


IONIZATION_ENERGY_EV = {"Si": 3.6, "SiC": 7.8}


def _position4(position: Sequence[float]) -> tuple[float, float, float, float]:
    values = tuple(map(float, position))
    if len(values) != 4:
        raise ValueError("Carrier positions must contain x, y, z, and time")
    return values[0], values[1], values[2], values[3]


def _point3(point: Sequence[float], *, label: str) -> tuple[float, float, float]:
    values = tuple(map(float, point))
    if len(values) != 3:
        raise ValueError(f"{label} must contain x, y, and z")
    return values[0], values[1], values[2]


@dataclass(frozen=True)
class CarrierGeneration:
    track_position: tuple[tuple[float, float, float, float], ...]
    ionized_pairs: tuple[float, ...]

    def __post_init__(self) -> None:
        if len(self.track_position) != len(self.ionized_pairs):
            raise ValueError("Carrier positions and populations must have equal length")
        if any(len(position) != 4 for position in self.track_position):
            raise ValueError("Carrier positions must contain x, y, z, and time")
        if any(
            population < 0 or not math.isfinite(population)
            for population in self.ionized_pairs
        ):
            raise ValueError("Carrier populations must be finite and non-negative")

    @property
    def total_pairs(self) -> float:
        return sum(self.ionized_pairs)


def from_energy_deposits(
    positions: Iterable[Sequence[float]],
    energies_mev: Iterable[float],
    *,
    material: str,
) -> CarrierGeneration:
    try:
        ionization_energy = IONIZATION_ENERGY_EV[material]
    except KeyError as exc:
        raise ValueError(
            f"Ionization energy is undefined for material {material}"
        ) from exc
    position_values = tuple(_position4(position) for position in positions)
    energy_values = tuple(map(float, energies_mev))
    if len(position_values) != len(energy_values):
        raise ValueError("Energy deposits and positions must have equal length")
    populations = tuple(energy * 1.0e6 / ionization_energy for energy in energy_values)
    return CarrierGeneration(position_values, populations)


def prescribed_track(
    start: Sequence[float],
    end: Sequence[float],
    *,
    packets: int,
    pairs_per_um: float,
    time: float = 0.0,
) -> CarrierGeneration:
    if packets <= 0:
        raise ValueError("Track packet count must be positive")
    if pairs_per_um < 0:
        raise ValueError("Track pairs per micrometre must be non-negative")
    start_xyz = _point3(start, label="Track start")
    end_xyz = _point3(end, label="Track end")
    displacement = tuple(
        end_value - start_value for start_value, end_value in zip(start_xyz, end_xyz)
    )
    length = math.sqrt(sum(value * value for value in displacement))
    if length == 0:
        raise ValueError("Track length must be positive")
    positions: tuple[tuple[float, float, float, float], ...] = tuple(
        (
            start_xyz[0] + displacement[0] * (index + 0.5) / packets,
            start_xyz[1] + displacement[1] * (index + 0.5) / packets,
            start_xyz[2] + displacement[2] * (index + 0.5) / packets,
            float(time),
        )
        for index in range(packets)
    )
    population = length * pairs_per_um / packets
    return CarrierGeneration(positions, (population,) * packets)
