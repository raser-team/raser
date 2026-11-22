"""Asynchronous sampling of analogue waveforms."""

import numpy as np

from .bandwidth import bandlimited_interpolate
from .settings import DigitizerSettings


def device_of(place, channels):
    """Return the device number for an electrode index and channel count."""
    if channels <= 0:
        raise ValueError("channels must be positive")
    return int(place) // int(channels)


def sample_count(bins, dt, period):
    """Return K from equation (2)."""
    if bins < 0 or dt <= 0 or period <= 0:
        raise ValueError("bins, dt, and period must be non-negative/positive")
    ratio = float(bins) * float(dt) / float(period)
    nearest = round(ratio)
    if abs(ratio - nearest) <= 1e-12 * max(1.0, abs(ratio)):
        ratio = nearest
    return int(np.floor(ratio))


def sample(
    voltage, dt, places, settings: DigitizerSettings, rng_of_device, rng_of_electrode
):
    """Return per-electrode first-sample offsets and sampled voltages.

    ``voltage`` has shape ``(electrodes, bins)`` in V and ``dt`` is the bin width
    in s. ``rng_of_device(device)`` returns the generator that draws the clock
    phase of a device; ``rng_of_electrode(place)`` returns the generator that
    draws the aperture jitter of an electrode. The sampling instants of an
    electrode are ``phase + k * T_s + delta_k`` after the first bin edge, in s.

    Returns ``phases`` with shape ``(electrodes,)`` in s and ``samples`` with
    shape ``(electrodes, K)`` in V.
    """
    values = np.asarray(voltage, dtype=np.float64)
    if values.ndim != 2:
        raise ValueError(
            f"voltage has shape {values.shape}, expected (electrodes, bins)"
        )
    places = [int(place) for place in places]
    if len(places) != values.shape[0]:
        raise ValueError("places must have one entry per voltage row")
    count = sample_count(values.shape[1], dt, settings.period_s)
    phases = np.empty(len(places), dtype=np.float64)
    phase_by_device = {}
    for row, place in enumerate(places):
        device = device_of(place, settings.channels)
        if device not in phase_by_device:
            phase_by_device[device] = float(
                rng_of_device(device).uniform(0.0, settings.period_s)
            )
        phases[row] = phase_by_device[device]
    samples = np.empty((len(places), count), dtype=np.float64)
    jitter = settings.aperture_jitter_s
    for row, place in enumerate(places):
        times = phases[row] + np.arange(count, dtype=np.float64) * settings.period_s
        if jitter > 0:
            times = times + rng_of_electrode(place).normal(0.0, jitter, count)
        samples[row] = bandlimited_interpolate(
            values[row : row + 1],
            dt,
            settings.response,
            settings.bandwidth_hz,
            times,
        )[0]
    return phases, samples
