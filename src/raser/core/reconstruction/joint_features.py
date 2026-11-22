"""Absolute integrals and complete pulse windows for two/three strip readouts."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .features import FeatureConfig, Features, _area, _leading


@dataclass(frozen=True)
class JointFeatureConfig(FeatureConfig):
    shape_ns: tuple[float, float] = (-0.5, 4.5)
    shape_samples: int = 256


def joint_features(
    times_s, signals, positions_um, *, config: JointFeatureConfig, waveform_kind
):
    """Read only supplied channels; retain absolute charge and relative pulse shape.

    Current integrals are fC. Frontend voltage integrals are explicitly mV ns
    charge proxies, requiring a separate transfer calibration for conversion.
    All pulse samples in the configured aligned window contribute to the vector.
    """
    n = len(signals)
    positions = np.asarray(positions_um, dtype=float)
    if (
        n not in (2, 3)
        or len(times_s) != n
        or positions.shape != (n, 2)
        or not np.isfinite(positions).all()
        or np.any(np.diff(positions[:, 0]) <= 0)
        or np.ptp(positions[:, 1]) > 1e-9
    ):
        raise ValueError("Joint strip features require two or three ordered readouts")
    if waveform_kind not in {"current_A", "frontend_mV"}:
        raise ValueError("Explicit current_A or frontend_mV waveform units required")
    area_factor, amplitude_scale = (
        (1e6, 1e-6) if waveform_kind == "current_A" else (1.0, 1.0)
    )
    negative, positive, amplitudes, noises, cfds, rises, axes, corrected = (
        [] for _ in range(8)
    )
    for ts, samples in zip(times_s, signals):
        t, v = np.asarray(ts, dtype=float) * 1e9, np.asarray(samples, dtype=float)
        if (
            t.ndim != 1
            or t.shape != v.shape
            or len(t) < 16
            or not np.isfinite(t).all()
            or not np.isfinite(v).all()
            or np.any(np.diff(t) <= 0)
        ):
            raise ValueError(
                "Finite increasing waveform times and matching samples required"
            )
        baseline = (t >= config.baseline_ns[0]) & (t <= config.baseline_ns[1])
        pulse = (t >= config.signal_ns[0]) & (t <= config.signal_ns[1])
        if baseline.sum() < 8 or pulse.sum() < 8:
            raise ValueError(
                "Waveform must cover the declared baseline and signal windows"
            )
        pedestal = float(np.median(v[baseline]))
        noise = max(
            config.noise_floor, float(1.4826 * np.median(abs(v[baseline] - pedestal)))
        )
        v = v - pedestal
        oriented, st = config.polarity * v[pulse], t[pulse]
        peak = int(np.argmax(oriented))
        amplitude = max(0.0, float(oriented[peak]))
        cfd = (
            _leading(st, oriented, peak, 0.5)
            if amplitude >= config.snr_threshold * noise
            else None
        )
        early = _leading(st, oriented, peak, 0.2) if cfd is not None else None
        late = _leading(st, oriented, peak, 0.8) if cfd is not None else None
        cfds.append(cfd)
        rises.append(late - early if late is not None and early is not None else 0.0)
        negative.append(area_factor * _area(np.maximum(-v[pulse], 0), st))
        positive.append(area_factor * _area(np.maximum(v[pulse], 0), st))
        amplitudes.append(amplitude)
        noises.append(noise)
        axes.append(t)
        corrected.append(v)
    neg, pos, amp, noise_array = (
        np.asarray(v) for v in (negative, positive, amplitudes, noises)
    )
    active = np.array([t is not None for t in cfds])
    anchor_index = int(np.argmax(np.where(active, amp, -1.0)))
    anchor_value = cfds[anchor_index] if active.any() else None
    anchor = float(anchor_value) if anchor_value is not None else 0.0
    relative = np.array([t - anchor if t is not None else 0.0 for t in cfds])
    shape_scale = max(sum(float(abs(v).max()) for v in corrected), np.finfo(float).tiny)
    grid = anchor + np.linspace(*config.shape_ns, config.shape_samples)
    shapes: list[float] = []
    for t, v in zip(axes, corrected):
        if grid[0] < t[0] or grid[-1] > t[-1]:
            raise ValueError("Waveform must cover the complete aligned pulse window")
        shapes.extend(np.interp(grid, t, v) / shape_scale)
    absolute_area = neg + pos
    fractions = absolute_area / max(float(absolute_area.sum()), np.finfo(float).tiny)
    values = np.r_[
        np.arcsinh(neg),
        np.arcsinh(pos),
        np.arcsinh(pos - neg),
        np.arcsinh(amp / amplitude_scale),
        fractions,
        relative,
        rises,
        active.astype(float),
        np.log1p(amp / noise_array),
        shapes,
    ]
    floors = np.r_[
        np.full(5 * n, 0.02),
        np.full(2 * n, 0.02),
        np.full(n, 0.1),
        np.full(n, 0.1),
        np.full(len(shapes), 0.01),
    ]
    if not np.isfinite(values).all():
        raise ArithmeticError("Nonfinite joint strip observations")
    return Features(
        values,
        floors,
        bool(active.any()),
        "ok" if active.any() else "no_significant_pulse",
        {
            "channel_count": n,
            "compact_feature_count": 9 * n,
            "active_channels": active.tolist(),
            "cfd_ns": cfds,
            "alignment_ns": anchor,
            "leading_rise_ns": rises,
            "amplitude": amplitudes,
            "baseline_noise": noises,
            "signed_integrals": (pos - neg).tolist(),
            "negative_integrals": negative,
            "positive_integrals": positive,
            "integral_units": "fC"
            if waveform_kind == "current_A"
            else "mV ns (charge proxy)",
            "shape_window_ns": list(config.shape_ns),
            "shape_samples_per_channel": config.shape_samples,
        },
    )
