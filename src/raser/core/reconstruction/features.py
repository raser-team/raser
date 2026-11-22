"""Truth-free features of trigger-referenced multichannel waveforms."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass

import numpy as np


@dataclass(frozen=True)
class FeatureConfig:
    baseline_ns: tuple[float, float] = (-10.0, -1.0)
    signal_ns: tuple[float, float] = (-0.5, 5.0)
    shape_ns: tuple[float, float] = (-0.3, 2.5)
    shape_samples: int = 32
    noise_floor: float = 0.001
    snr_threshold: float = 5.0
    polarity: int = -1

    def __post_init__(self):
        for window in (self.baseline_ns, self.signal_ns, self.shape_ns):
            if (
                len(window) != 2
                or not all(math.isfinite(x) for x in window)
                or window[0] >= window[1]
            ):
                raise ValueError(
                    "Feature windows must be finite increasing pairs in ns"
                )
        if self.baseline_ns[1] >= self.signal_ns[0]:
            raise ValueError("Baseline and signal windows must be disjoint")
        if (
            type(self.shape_samples) is not int
            or self.shape_samples < 4
            or self.polarity not in (-1, 1)
        ):
            raise ValueError("Invalid shape sample count or pulse polarity")
        if (
            not math.isfinite(self.noise_floor)
            or self.noise_floor <= 0
            or not math.isfinite(self.snr_threshold)
            or self.snr_threshold <= 0
        ):
            raise ValueError("Noise floor and SNR threshold must be positive")

    def as_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class Features:
    values: np.ndarray
    floors: np.ndarray
    usable: bool
    reason: str
    diagnostics: dict


def _area(values: np.ndarray, times: np.ndarray) -> float:
    return float(np.sum((values[:-1] + values[1:]) * np.diff(times) / 2.0))


def _leading(
    times: np.ndarray, values: np.ndarray, peak: int, fraction: float
) -> float | None:
    level = fraction * values[peak]
    candidates = np.flatnonzero(
        (values[:peak] < level) & (values[1 : peak + 1] >= level)
    )
    if not len(candidates):
        return None
    i = int(candidates[-1])
    return float(
        times[i]
        + (level - values[i]) / (values[i + 1] - values[i]) * (times[i + 1] - times[i])
    )


def extract_features(
    times_s, signals, positions_um, *, mode: str, config: FeatureConfig
) -> Features:
    """Areas, relative CFD times and normalized pulse shapes; no trajectory input."""
    if mode not in {"charge", "time", "joint"}:
        raise ValueError("Feature mode must be charge, time or joint")
    positions = np.asarray(positions_um, dtype=float)
    if (
        positions.ndim != 2
        or positions.shape[1] != 2
        or len(positions) != len(signals)
        or not np.isfinite(positions).all()
    ):
        raise ValueError("One finite local (x,y) position is required per channel")
    if len(signals) < 3 or len(times_s) != len(signals):
        raise ValueError("At least three complete waveform channels are required")
    baselined, axes, negative_areas, positive_areas, amplitudes, noises = (
        [],
        [],
        [],
        [],
        [],
        [],
    )
    cfds, rises = [], []
    for times, samples in zip(times_s, signals):
        t = np.asarray(times, dtype=float) * 1e9
        v = np.asarray(samples, dtype=float)
        if (
            t.ndim != 1
            or v.shape != t.shape
            or len(t) < 16
            or not np.isfinite(t).all()
            or not np.isfinite(v).all()
            or np.any(np.diff(t) <= 0)
        ):
            raise ValueError(
                "Waveforms require finite increasing times and matching samples"
            )
        baseline = (t >= config.baseline_ns[0]) & (t <= config.baseline_ns[1])
        pulse = (t >= config.signal_ns[0]) & (t <= config.signal_ns[1])
        if np.count_nonzero(baseline) < 8 or np.count_nonzero(pulse) < 8:
            raise ValueError("Waveform does not cover baseline and signal windows")
        pedestal = float(np.median(v[baseline]))
        noise = max(
            config.noise_floor,
            float(1.4826 * np.median(np.abs(v[baseline] - pedestal))),
        )
        corrected = v - pedestal
        st, sv = t[pulse], corrected[pulse]
        oriented = config.polarity * sv
        peak = int(np.argmax(oriented))
        amp = max(0.0, float(oriented[peak]))
        cfd = (
            _leading(st, oriented, peak, 0.5)
            if amp >= config.snr_threshold * noise
            else None
        )
        early = _leading(st, oriented, peak, 0.2) if cfd is not None else None
        late = _leading(st, oriented, peak, 0.8) if cfd is not None else None
        cfds.append(cfd)
        rises.append(late - early if early is not None and late is not None else 0.0)
        # Integrals are in input amplitude units * ns (voltage-area proxies for frontend data).
        negative_areas.append(_area(np.maximum(-sv, 0), st))
        positive_areas.append(_area(np.maximum(sv, 0), st))
        amplitudes.append(amp)
        noises.append(noise)
        baselined.append(corrected)
        axes.append(t)
    active = np.array([t is not None for t in cfds])
    amp_array = np.asarray(amplitudes)
    area = float(sum(negative_areas) + sum(positive_areas))
    charge = (
        np.r_[negative_areas, positive_areas] / area
        if area > 0
        else np.zeros(2 * len(signals))
    )
    charge = np.r_[
        charge, amp_array / max(float(amp_array.sum()), np.finfo(float).tiny)
    ]
    reference = (
        float(np.mean([t for t in cfds if t is not None])) if active.any() else 0.0
    )
    timing = np.r_[
        [t - reference if t is not None else 0.0 for t in cfds],
        rises,
        active.astype(float),
    ]
    charge_floors = np.full(len(charge), 0.01)
    timing_floors = np.r_[np.full(2 * len(signals), 0.02), np.full(len(signals), 0.1)]
    usable, reason = (
        bool(active.any()),
        "ok" if active.any() else "no_significant_pulse",
    )
    if mode == "time":
        # At least three timings and two independent spatial directions for a pixel plane.
        spatial_rank = (
            np.linalg.matrix_rank(positions[active] - positions[active].mean(axis=0))
            if active.any()
            else 0
        )
        required_rank = (
            2 if np.linalg.matrix_rank(positions - positions.mean(axis=0)) == 2 else 1
        )
        if active.sum() < 3 or spatial_rank < required_rank:
            usable, reason = False, "insufficient_independent_timings"
        values, floors = timing, timing_floors
    elif mode == "charge":
        values, floors = charge, charge_floors
    else:
        # Common alignment removes event time while retaining interchannel delays.
        trigger_channel = int(np.argmax(np.where(active, amp_array, -1.0)))
        anchor = cfds[trigger_channel]
        if active.any() and anchor is None:
            raise ArithmeticError("Active timing channel is missing its CFD time")
        alignment = anchor if anchor is not None else 0.0
        grid = alignment + np.linspace(*config.shape_ns, config.shape_samples)
        shape = []
        scale = max(float(amp_array.sum()), np.finfo(float).tiny)
        for t, v in zip(axes, baselined):
            if grid[0] < t[0] or grid[-1] > t[-1]:
                raise ValueError(
                    "Waveform does not cover the aligned pulse-shape window"
                )
            shape.extend(np.interp(grid, t, v) / scale)
        values = np.r_[charge, timing, shape]
        floors = np.r_[charge_floors, timing_floors, np.full(len(shape), 0.01)]
    if not np.isfinite(values).all():
        raise ValueError("Nonfinite waveform features")
    return Features(
        values,
        floors,
        usable,
        reason,
        {
            "active_channels": active.tolist(),
            "cfd_ns": cfds,
            "leading_rise_ns": rises,
            "amplitude": amplitudes,
            "baseline_noise": noises,
            "negative_area_input_units_ns": negative_areas,
            "positive_area_input_units_ns": positive_areas,
        },
    )
