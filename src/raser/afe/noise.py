#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

"""
Noise waveform synthesis from a one-sided spectral density.
"""

import logging
import os
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


def load_noise_spectrum(
    path: str,
    frequency_column: int = 0,
    density_column: int = 1,
) -> tuple[np.ndarray, np.ndarray]:
    """Load a two-column noise spectrum file.

    The expected input is an ngspice ``wrdata`` style text file. Non-numeric
    header/comment lines are ignored. Duplicate frequencies are averaged.
    """
    frequencies = []
    densities = []
    column_count = max(frequency_column, density_column) + 1

    with open(path, "r") as spectrum_file:
        for line in spectrum_file:
            stripped = line.strip()
            if not stripped or stripped.startswith(("#", "*")):
                continue

            fields = stripped.replace(",", " ").split()
            if len(fields) < column_count:
                continue

            try:
                frequency = float(fields[frequency_column])
                density = float(fields[density_column])
            except ValueError:
                continue

            if (
                np.isfinite(frequency)
                and np.isfinite(density)
                and frequency >= 0.0
                and density >= 0.0
            ):
                frequencies.append(frequency)
                densities.append(density)

    if len(frequencies) < 2:
        raise ValueError(f"Noise spectrum file has fewer than two valid points: {path}")

    frequencies = np.asarray(frequencies, dtype=np.float64)
    densities = np.asarray(densities, dtype=np.float64)
    order = np.argsort(frequencies)
    frequencies = frequencies[order]
    densities = densities[order]

    unique_frequencies, inverse = np.unique(frequencies, return_inverse=True)
    summed_densities = np.zeros_like(unique_frequencies, dtype=np.float64)
    counts = np.zeros_like(unique_frequencies, dtype=np.float64)
    np.add.at(summed_densities, inverse, densities)
    np.add.at(counts, inverse, 1.0)

    return unique_frequencies, summed_densities / counts


def resolve_noise_spectrum_path(path: str, base_dir: Optional[str] = None) -> str:
    """Resolve an absolute or relative noise spectrum path."""
    if os.path.isabs(path):
        return path

    candidates = []
    if base_dir is not None:
        candidates.append(os.path.abspath(os.path.join(base_dir, path)))
    candidates.append(os.path.abspath(path))

    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate

    return candidates[0]


def estimate_noise_spectrum(
    waveforms,
    time_step_s: float,
    *,
    segment_length: Optional[int] = None,
    overlap: float = 0.5,
    window: str = "hann",
    density_type: str = "amplitude",
    remove_mean: bool = True,
    min_frequency_hz: Optional[float] = None,
    max_frequency_hz: Optional[float] = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Estimate a one-sided noise spectrum from baseline/no-signal waveforms.

    The estimator is a NumPy-only Welch average. Input samples are assumed to
    already be in the desired output unit, for example mV. With
    ``density_type="amplitude"`` the returned values are ASD in unit/sqrt(Hz);
    with ``density_type="power"`` they are PSD in unit^2/Hz.
    """
    time_step_s = float(time_step_s)
    if time_step_s <= 0.0:
        raise ValueError("time_step_s must be positive")

    samples = np.asarray(waveforms, dtype=np.float64)
    if samples.ndim == 1:
        samples = samples[np.newaxis, :]
    elif samples.ndim != 2:
        raise ValueError("waveforms must be a one- or two-dimensional array")

    if samples.shape[1] < 2:
        raise ValueError("waveforms must contain at least two samples")

    n_samples = samples.shape[1]
    if segment_length is None:
        segment_length = n_samples
    segment_length = int(segment_length)
    if segment_length < 2 or segment_length > n_samples:
        raise ValueError("segment_length must be between 2 and waveform length")

    overlap_samples = _overlap_samples(overlap, segment_length)
    step = segment_length - overlap_samples
    if step <= 0:
        raise ValueError("overlap leaves no step between Welch segments")

    taper = _window_samples(window, segment_length)
    window_power = float(np.sum(np.square(taper)))
    if window_power <= 0.0:
        raise ValueError("window has zero power")

    sample_rate_hz = 1.0 / time_step_s
    scale = sample_rate_hz * window_power
    psd_sum = None
    segment_count = 0

    for waveform in samples:
        finite = np.isfinite(waveform)
        if not np.all(finite):
            if not np.any(finite):
                continue
            waveform = waveform.copy()
            waveform[~finite] = np.nanmean(waveform[finite])

        for start in range(0, n_samples - segment_length + 1, step):
            segment = waveform[start:start + segment_length]
            if remove_mean:
                segment = segment - np.mean(segment)
            spectrum = np.fft.rfft(segment * taper)
            psd = np.square(np.abs(spectrum)) / scale
            if segment_length % 2 == 0:
                psd[1:-1] *= 2.0
            else:
                psd[1:] *= 2.0

            if psd_sum is None:
                psd_sum = np.zeros_like(psd)
            psd_sum += psd
            segment_count += 1

    if segment_count == 0 or psd_sum is None:
        raise ValueError("no Welch segments were available")

    frequencies_hz = np.fft.rfftfreq(segment_length, d=time_step_s)
    psd_average = psd_sum / float(segment_count)

    mask = np.ones(frequencies_hz.shape, dtype=bool)
    if min_frequency_hz is not None:
        min_frequency_hz = float(min_frequency_hz)
        if min_frequency_hz < 0.0:
            raise ValueError("min_frequency_hz must be non-negative")
        mask &= frequencies_hz >= min_frequency_hz
    if max_frequency_hz is not None:
        max_frequency_hz = float(max_frequency_hz)
        if max_frequency_hz <= 0.0:
            raise ValueError("max_frequency_hz must be positive")
        mask &= frequencies_hz <= max_frequency_hz

    density_key = density_type.lower()
    if density_key in ("amplitude", "asd", "sqrt_psd", "sqrt"):
        density = np.sqrt(psd_average)
    elif density_key in ("power", "psd"):
        density = psd_average
    else:
        raise ValueError(f"Unsupported density_type: {density_type}")

    return frequencies_hz[mask], density[mask]


def write_noise_spectrum(path: str, frequencies_hz, spectral_density) -> None:
    """Write a two-column spectrum file compatible with load_noise_spectrum."""
    frequencies_hz = np.asarray(frequencies_hz, dtype=np.float64)
    spectral_density = np.asarray(spectral_density, dtype=np.float64)
    if frequencies_hz.shape != spectral_density.shape:
        raise ValueError("frequencies_hz and spectral_density must have the same shape")
    with open(path, "w") as output_file:
        for frequency, density in zip(frequencies_hz, spectral_density):
            output_file.write(f"{frequency:.8e} {density:.8e}\n")


def integrate_noise_spectrum_rms(
    frequencies_hz,
    spectral_density,
    *,
    density_type: str = "amplitude",
    unit_scale: float = 1.0,
    min_frequency_hz: Optional[float] = None,
    max_frequency_hz: Optional[float] = None,
) -> float:
    """Integrate a one-sided spectrum into time-domain RMS."""
    frequencies_hz = np.asarray(frequencies_hz, dtype=np.float64)
    spectral_density = np.asarray(spectral_density, dtype=np.float64)
    if frequencies_hz.ndim != 1 or spectral_density.ndim != 1:
        raise ValueError("frequencies_hz and spectral_density must be one-dimensional")
    if frequencies_hz.size != spectral_density.size:
        raise ValueError("frequencies_hz and spectral_density must have the same length")

    finite = np.isfinite(frequencies_hz) & np.isfinite(spectral_density)
    finite &= (frequencies_hz >= 0.0) & (spectral_density >= 0.0)
    frequencies_hz = frequencies_hz[finite]
    spectral_density = spectral_density[finite]
    if frequencies_hz.size < 2:
        raise ValueError("at least two finite spectral-density points are required")

    order = np.argsort(frequencies_hz)
    frequencies_hz = frequencies_hz[order]
    spectral_density = spectral_density[order]

    density_key = density_type.lower()
    if density_key in ("amplitude", "asd", "sqrt_psd", "sqrt"):
        psd = np.square(spectral_density * float(unit_scale))
    elif density_key in ("power", "psd"):
        psd = spectral_density * float(unit_scale) * float(unit_scale)
    else:
        raise ValueError(f"Unsupported density_type: {density_type}")

    if min_frequency_hz is not None:
        min_frequency_hz = float(min_frequency_hz)
        if min_frequency_hz < 0.0:
            raise ValueError("min_frequency_hz must be non-negative")
    else:
        min_frequency_hz = 0.0

    if max_frequency_hz is not None:
        max_frequency_hz = float(max_frequency_hz)
        if max_frequency_hz <= 0.0:
            raise ValueError("max_frequency_hz must be positive")
    else:
        max_frequency_hz = frequencies_hz[-1]

    if max_frequency_hz <= min_frequency_hz:
        return 0.0

    frequencies_hz, psd = _slice_spectrum_for_integration(
        frequencies_hz,
        psd,
        min_frequency_hz,
        max_frequency_hz,
    )
    if frequencies_hz.size < 2:
        return 0.0

    return float(np.sqrt(np.trapz(psd, frequencies_hz)))


def synthesize_noise_from_spectrum(
    frequencies_hz,
    spectral_density,
    n_samples: int,
    time_step_s: float,
    *,
    seed=None,
    density_type: str = "amplitude",
    unit_scale: float = 1.0,
    mean: float = 0.0,
    target_rms: Optional[float] = None,
    min_frequency_hz: Optional[float] = None,
    max_frequency_hz: Optional[float] = None,
    randomize_amplitude: bool = True,
) -> np.ndarray:
    """Generate a real time-domain noise waveform from a one-sided spectrum.

    ``density_type="amplitude"`` means the input is amplitude spectral density
    in output-units/sqrt(Hz), for example ngspice ``onoise_spectrum``. Use
    ``density_type="power"`` for one-sided PSD in output-units^2/Hz.
    """
    n_samples = int(n_samples)
    time_step_s = float(time_step_s)
    if n_samples <= 0:
        raise ValueError("n_samples must be positive")
    if time_step_s <= 0.0:
        raise ValueError("time_step_s must be positive")

    frequencies_hz = np.asarray(frequencies_hz, dtype=np.float64)
    spectral_density = np.asarray(spectral_density, dtype=np.float64)
    if frequencies_hz.ndim != 1 or spectral_density.ndim != 1:
        raise ValueError("frequencies_hz and spectral_density must be one-dimensional")
    if frequencies_hz.size != spectral_density.size:
        raise ValueError("frequencies_hz and spectral_density must have the same length")
    if frequencies_hz.size < 2:
        raise ValueError("at least two spectral-density points are required")

    finite = np.isfinite(frequencies_hz) & np.isfinite(spectral_density)
    finite &= (frequencies_hz >= 0.0) & (spectral_density >= 0.0)
    frequencies_hz = frequencies_hz[finite]
    spectral_density = spectral_density[finite]
    if frequencies_hz.size < 2:
        raise ValueError("at least two finite spectral-density points are required")

    order = np.argsort(frequencies_hz)
    frequencies_hz = frequencies_hz[order]
    spectral_density = spectral_density[order]

    fft_frequencies = np.fft.rfftfreq(n_samples, d=time_step_s)
    density_grid = np.interp(
        fft_frequencies,
        frequencies_hz,
        spectral_density,
        left=0.0,
        right=0.0,
    )

    density_key = density_type.lower()
    if density_key in ("amplitude", "asd", "sqrt_psd", "sqrt"):
        psd_grid = np.square(density_grid * unit_scale)
    elif density_key in ("power", "psd"):
        psd_grid = density_grid * unit_scale * unit_scale
    else:
        raise ValueError(f"Unsupported density_type: {density_type}")

    if min_frequency_hz is not None:
        min_frequency_hz = float(min_frequency_hz)
        if min_frequency_hz < 0.0:
            raise ValueError("min_frequency_hz must be non-negative")
        psd_grid = np.where(fft_frequencies >= min_frequency_hz, psd_grid, 0.0)

    if max_frequency_hz is not None:
        max_frequency_hz = float(max_frequency_hz)
        if max_frequency_hz <= 0.0:
            raise ValueError("max_frequency_hz must be positive")
        psd_grid = np.where(fft_frequencies <= max_frequency_hz, psd_grid, 0.0)

    rng = np.random.default_rng(seed)
    spectrum = np.zeros(fft_frequencies.shape, dtype=np.complex128)
    df = 1.0 / (n_samples * time_step_s)

    if n_samples % 2 == 0:
        interior = np.arange(1, len(fft_frequencies) - 1)
        nyquist_index = len(fft_frequencies) - 1
    else:
        interior = np.arange(1, len(fft_frequencies))
        nyquist_index = None

    if interior.size > 0:
        if randomize_amplitude:
            sigma = n_samples * np.sqrt(psd_grid[interior] * df) / 2.0
            real = rng.normal(0.0, sigma)
            imag = rng.normal(0.0, sigma)
            spectrum[interior] = real + 1j * imag
        else:
            amplitude = n_samples * np.sqrt(psd_grid[interior] * df / 2.0)
            phase = rng.uniform(0.0, 2.0 * np.pi, size=interior.size)
            spectrum[interior] = amplitude * (np.cos(phase) + 1j * np.sin(phase))

    if nyquist_index is not None:
        amplitude = n_samples * np.sqrt(psd_grid[nyquist_index] * df)
        if randomize_amplitude:
            spectrum[nyquist_index] = rng.normal(0.0, amplitude)
        else:
            spectrum[nyquist_index] = amplitude * rng.choice((-1.0, 1.0))

    noise = np.fft.irfft(spectrum, n=n_samples)
    noise = np.asarray(noise, dtype=np.float64)
    noise -= np.mean(noise)

    if target_rms is not None:
        noise = _normalize_noise(noise, target_rms, "target_rms")

    noise += float(mean)
    return noise


def _slice_spectrum_for_integration(
    frequencies_hz: np.ndarray,
    psd: np.ndarray,
    min_frequency_hz: float,
    max_frequency_hz: float,
) -> tuple[np.ndarray, np.ndarray]:
    lower = max(min_frequency_hz, frequencies_hz[0])
    upper = min(max_frequency_hz, frequencies_hz[-1])
    if upper <= lower:
        return np.asarray([], dtype=np.float64), np.asarray([], dtype=np.float64)

    mask = (frequencies_hz >= lower) & (frequencies_hz <= upper)
    sliced_frequencies = frequencies_hz[mask]
    sliced_psd = psd[mask]

    if sliced_frequencies.size == 0 or sliced_frequencies[0] > lower:
        lower_psd = np.interp(lower, frequencies_hz, psd)
        sliced_frequencies = np.insert(sliced_frequencies, 0, lower)
        sliced_psd = np.insert(sliced_psd, 0, lower_psd)

    if sliced_frequencies[-1] < upper:
        upper_psd = np.interp(upper, frequencies_hz, psd)
        sliced_frequencies = np.append(sliced_frequencies, upper)
        sliced_psd = np.append(sliced_psd, upper_psd)

    return sliced_frequencies, sliced_psd


def _overlap_samples(overlap, segment_length: int) -> int:
    if isinstance(overlap, float):
        if overlap < 0.0 or overlap >= 1.0:
            raise ValueError("fractional overlap must be in [0, 1)")
        return int(round(overlap * segment_length))

    overlap_samples = int(overlap)
    if overlap_samples < 0 or overlap_samples >= segment_length:
        raise ValueError("overlap samples must be in [0, segment_length)")
    return overlap_samples


def _window_samples(window: str, segment_length: int) -> np.ndarray:
    key = str(window).lower()
    if key in ("hann", "hanning"):
        return np.hanning(segment_length)
    if key in ("boxcar", "rectangular", "rect", "none"):
        return np.ones(segment_length, dtype=np.float64)
    if key == "blackman":
        return np.blackman(segment_length)
    raise ValueError(f"Unsupported window: {window}")


def _normalize_noise(noise: np.ndarray, target_rms, label: str) -> np.ndarray:
    target_rms = float(target_rms)
    if target_rms < 0.0:
        raise ValueError(f"{label} must be non-negative")

    current_rms = float(np.std(noise))
    if target_rms == 0.0:
        noise.fill(0.0)
    elif current_rms > 0.0:
        noise *= target_rms / current_rms
    else:
        logger.warning("Cannot normalize zero-RMS spectral noise to %s", target_rms)
    return noise
