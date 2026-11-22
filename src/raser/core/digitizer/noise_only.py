"""Direct sampling of stationary noise-only channels."""

import numpy as np

from raser.core.readout.spectral_noise import noise_from_spectrum

from .bandwidth import response_values
from .quantize import quantize
from .settings import DigitizerSettings, number


def noise_only_channels(deposited_keV, trigger_places, cut_keV):
    """Return non-trigger channels whose deposited energy is below ``cut_keV``.

    ``deposited_keV`` has one energy per electrode, ``trigger_places`` is a
    sequence of electrode indices (possibly empty), ``cut_keV`` is a finite number.
    """
    cut = number(cut_keV, "cut_keV")
    energies = np.asarray(deposited_keV, dtype=np.float64)
    if energies.ndim != 1:
        raise ValueError("deposited_keV must be one-dimensional")
    trigger = {int(place) for place in trigger_places}
    return [
        place
        for place, energy in enumerate(energies)
        if place not in trigger and energy < cut
    ]


def _validate_spectrum(frequencies_hz, density):
    frequencies = np.asarray(frequencies_hz, dtype=np.float64)
    values = np.asarray(density, dtype=np.float64)
    if frequencies.ndim != 1 or values.ndim != 1 or frequencies.shape != values.shape:
        raise ValueError(
            "frequencies_hz and density must be one-dimensional arrays of equal length"
        )
    if (
        frequencies.size < 2
        or np.any(~np.isfinite(frequencies))
        or np.any(frequencies < 0)
        or np.any(np.diff(frequencies) <= 0)
    ):
        raise ValueError(
            "frequencies_hz must contain at least two increasing non-negative finite values"
        )
    if np.any(~np.isfinite(values)) or np.any(values < 0):
        raise ValueError("density must contain finite non-negative values")
    return frequencies, values


def sampled_density(frequencies_hz, density, response, bandwidth_hz, sampling_rate_hz):
    """Fold an analogue one-sided density through equation (6)."""
    frequencies, values = _validate_spectrum(frequencies_hz, density)
    sampling_rate = float(sampling_rate_hz)
    if not np.isfinite(sampling_rate) or sampling_rate <= 0:
        raise ValueError("sampling_rate_hz must be positive and finite")
    nyquist = 0.5 * sampling_rate
    points = max(2, frequencies.size, 1024)
    grid = np.linspace(0.0, nyquist, points, dtype=np.float64)
    maximum = frequencies[-1]
    aliases = np.arange(
        -int(np.ceil(maximum / sampling_rate)) - 1,
        int(np.ceil(maximum / sampling_rate)) + 2,
        dtype=np.int64,
    )
    folded = []
    for frequency in frequencies:
        positions = np.abs(frequency - aliases * sampling_rate)
        folded.extend(positions[positions <= nyquist])
    if folded:
        grid = np.unique(np.concatenate((grid, np.asarray(folded, dtype=np.float64))))
    total_power = np.zeros_like(grid)
    for alias in aliases:
        argument = np.abs(grid + alias * sampling_rate)
        source = np.interp(argument, frequencies, values, left=0.0, right=0.0)
        transfer = response_values(argument, response, bandwidth_hz)
        total_power += source * source * transfer * transfer
    return grid, np.sqrt(total_power)


def noise_codes(sampled, count, period, settings: DigitizerSettings, generator):
    """Draw and quantise one stationary noise-only waveform."""
    frequencies_hz, density = sampled
    count = int(count)
    if count < 0:
        raise ValueError("count must be non-negative")
    values = noise_from_spectrum(
        frequencies_hz, density, count, float(period), generator
    )
    codes, clipped = quantize(values[None, :], settings)
    return codes[0], int(clipped[0])
