"""Zero-phase analogue response filtering and band-limited interpolation."""

import numpy as np


def _validate_voltage(voltage, dt):
    values = np.asarray(voltage, dtype=np.float64)
    if values.ndim != 2:
        raise ValueError(
            f"voltage has shape {values.shape}, expected (electrodes, bins)"
        )
    if not np.isfinite(dt) or dt <= 0:
        raise ValueError("dt must be positive")
    return values


def response_values(frequencies_hz, response, bandwidth_hz=None):
    """Return the magnitude response in equation (1)."""
    frequencies = np.asarray(frequencies_hz, dtype=np.float64)
    if response == "none":
        if bandwidth_hz is not None:
            raise ValueError("bandwidth_hz must be absent for response 'none'")
        return np.ones_like(frequencies)
    if response != "brickwall":
        raise ValueError("response must be 'brickwall' or 'none'")
    if bandwidth_hz is None or not np.isfinite(bandwidth_hz) or bandwidth_hz <= 0:
        raise ValueError("bandwidth_hz must be positive for response 'brickwall'")
    return (frequencies <= float(bandwidth_hz)).astype(np.float64)


def _detrended_spectrum(voltage, dt, response, bandwidth_hz):
    values = _validate_voltage(voltage, dt)
    bins = values.shape[1]
    centres = (np.arange(bins, dtype=np.float64) + 0.5) * dt
    if bins <= 1:
        slopes = np.zeros(values.shape[0], dtype=np.float64)
    else:
        slopes = (values[:, -1] - values[:, 0]) / ((bins - 1) * dt)
    trend = values[:, :1] + slopes[:, None] * (centres[None, :] - centres[0])
    residual = values - trend
    frequencies = np.fft.rfftfreq(bins, dt)
    transfer = response_values(frequencies, response, bandwidth_hz)
    spectrum = np.fft.rfft(residual, axis=1) * transfer[None, :]
    return spectrum, trend[:, 0], slopes, centres[0], frequencies


def filter_waveform(voltage, dt, response, bandwidth_hz=None):
    """Filter a waveform at its original bin centres."""
    values = _validate_voltage(voltage, dt)
    if values.shape[1] == 0:
        return values.copy()
    spectrum, first, slopes, first_centre, _ = _detrended_spectrum(
        values, dt, response, bandwidth_hz
    )
    filtered = np.fft.irfft(spectrum, n=values.shape[1], axis=1)
    centres = (np.arange(values.shape[1], dtype=np.float64) + 0.5) * dt
    trend = first[:, None] + slopes[:, None] * (centres[None, :] - first_centre)
    return filtered + trend


def bandlimited_interpolate(
    voltage, dt, response, bandwidth_hz, times, chunk_size=100_000
):
    """Evaluate equation (7) at arbitrary times."""
    values = _validate_voltage(voltage, dt)
    times = np.asarray(times, dtype=np.float64)
    if times.ndim != 1:
        raise ValueError("times must be one-dimensional")
    if not np.isfinite(times).all():
        raise ValueError("times must be finite")
    if values.shape[1] == 0:
        return np.empty((values.shape[0], times.size), dtype=np.float64)
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")

    spectrum, first, slopes, first_centre, frequencies = _detrended_spectrum(
        values, dt, response, bandwidth_hz
    )
    bins = values.shape[1]
    weights = np.full(frequencies.shape, 2.0, dtype=np.float64)
    weights[0] = 1.0
    if bins % 2 == 0:
        weights[-1] = 1.0
    result = np.empty((values.shape[0], times.size), dtype=np.float64)
    block = min(int(chunk_size), max(1, 5_000_000 // frequencies.size))
    for start in range(0, times.size, block):
        stop = min(start + block, times.size)
        phase = np.exp(
            2j * np.pi * frequencies[:, None] * (times[None, start:stop] - first_centre)
        )
        filtered = (
            np.real(np.einsum("ek,kj->ej", spectrum * weights[None, :], phase)) / bins
        )
        trend = first[:, None] + slopes[:, None] * (
            times[None, start:stop] - first_centre
        )
        result[:, start:stop] = filtered + trend
    return result
