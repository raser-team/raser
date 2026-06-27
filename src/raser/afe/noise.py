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
