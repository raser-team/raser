"""Measurements derived from one sampled waveform."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np


@dataclass(frozen=True)
class WaveformMeasurements:
    amplitude: float
    time_of_arrival: float | None
    time_over_threshold: float | None
    charge: float
    constant_fraction_time: float | None


def _crossing(
    times: np.ndarray, values: np.ndarray, threshold: float, start: int, stop: int
) -> float | None:
    for index in range(start, stop):
        left = values[index] - threshold
        right = values[index + 1] - threshold
        if left == 0:
            return float(times[index])
        if right == 0:
            return float(times[index + 1])
        if left < 0 < right or left > 0 > right:
            fraction = abs(left) / (abs(left) + abs(right))
            return float(times[index] + fraction * (times[index + 1] - times[index]))
    return None


def measure_waveform(
    times: Sequence[float],
    samples: Sequence[float],
    *,
    threshold: float,
    constant_fraction: float = 0.5,
) -> WaveformMeasurements:
    time_values = np.asarray(times, dtype=np.float64)
    sample_values = np.asarray(samples, dtype=np.float64)
    if (
        time_values.ndim != 1
        or sample_values.ndim != 1
        or len(time_values) != len(sample_values)
    ):
        raise ValueError("Waveform times and samples must be equal-length vectors")
    if len(time_values) < 2 or np.any(np.diff(time_values) <= 0):
        raise ValueError("Waveform times must contain increasing samples")
    if threshold < 0:
        raise ValueError("Waveform threshold must be non-negative")
    if not 0 < constant_fraction < 1:
        raise ValueError("Constant fraction must lie between zero and one")

    magnitudes = np.abs(sample_values)
    peak_index = int(np.argmax(magnitudes))
    amplitude = float(magnitudes[peak_index])
    toa = _crossing(time_values, magnitudes, threshold, 0, peak_index)
    trailing = _crossing(
        time_values, magnitudes, threshold, peak_index, len(time_values) - 1
    )
    tot = trailing - toa if toa is not None and trailing is not None else None
    cfd = _crossing(
        time_values,
        magnitudes,
        constant_fraction * amplitude,
        0,
        peak_index,
    )
    charge = float(
        np.sum((sample_values[:-1] + sample_values[1:]) * np.diff(time_values) / 2.0)
    )
    return WaveformMeasurements(amplitude, toa, tot, charge, cfd)
