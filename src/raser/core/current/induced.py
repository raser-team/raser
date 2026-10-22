"""Ramo-potential induced currents for transported carrier paths."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping, Sequence


Point = tuple[float, float, float]
WeightingPotential = Callable[[Point], float]


def _point3(point: Sequence[float]) -> Point:
    values = tuple(map(float, point))
    if len(values) != 3:
        raise ValueError("Carrier path points must contain x, y, and z")
    return values[0], values[1], values[2]


@dataclass(frozen=True)
class NortonCurrent:
    times: tuple[float, ...]
    values: Mapping[str, tuple[float, ...]]

    def __post_init__(self) -> None:
        if not self.times:
            raise ValueError("Induced current requires time samples")
        if any(later <= earlier for earlier, later in zip(self.times, self.times[1:])):
            raise ValueError("Current time samples must increase")
        if any(len(samples) != len(self.times) for samples in self.values.values()):
            raise ValueError("Each electrode current must share the current time axis")


def induced_currents(
    *,
    charge_coulomb: float,
    times: Sequence[float],
    positions: Sequence[Sequence[float]],
    weighting_potentials: Mapping[str, WeightingPotential],
) -> NortonCurrent:
    time_values = tuple(map(float, times))
    point_values = tuple(_point3(point) for point in positions)
    if len(point_values) != len(time_values):
        raise ValueError("Carrier path positions and times must have equal length")
    if not weighting_potentials:
        raise ValueError("Induced current requires weighting potentials")

    current_times = tuple(
        (start_time + end_time) / 2.0
        for start_time, end_time in zip(time_values, time_values[1:])
    )
    values = {}
    for electrode, weighting in weighting_potentials.items():
        samples = []
        for index, (start_time, end_time) in enumerate(
            zip(time_values, time_values[1:])
        ):
            delta_t = end_time - start_time
            if delta_t <= 0:
                raise ValueError("Carrier path times must increase")
            induced_charge = charge_coulomb * (
                float(weighting(point_values[index + 1]))
                - float(weighting(point_values[index]))
            )
            samples.append(induced_charge / delta_t)
        values[str(electrode)] = tuple(samples)
    return NortonCurrent(current_times, values)
