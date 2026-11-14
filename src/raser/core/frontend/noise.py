"""Frontend noise spectra and time-domain synthesis."""

from __future__ import annotations

import math
from pathlib import Path
from typing import TypeAlias

import numpy as np
from numpy.typing import NDArray


ELEMENTARY_CHARGE_C = 1.602176634e-19
FloatArray: TypeAlias = NDArray[np.float64]


def load_noise_spectrum(
    path: str | Path,
    *,
    frequency_column: int = 0,
    density_column: int = 1,
) -> tuple[FloatArray, FloatArray]:
    """Load an ngspice-style one-sided noise spectrum."""
    if frequency_column < 0 or density_column < 0:
        raise ValueError("Noise spectrum columns must be non-negative")
    column_count = max(frequency_column, density_column) + 1
    frequencies: list[float] = []
    densities: list[float] = []

    spectrum_path = Path(path)
    for line_number, line in enumerate(
        spectrum_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "*")):
            continue
        fields = stripped.replace(",", " ").split()
        if len(fields) < column_count:
            raise ValueError(
                f"Noise spectrum row {line_number} has {len(fields)} columns; "
                f"expected at least {column_count}"
            )
        try:
            frequency = float(fields[frequency_column])
            density = float(fields[density_column])
        except ValueError as error:
            raise ValueError(
                f"Noise spectrum row {line_number} contains non-numeric data"
            ) from error
        if not math.isfinite(frequency) or frequency < 0.0:
            raise ValueError(
                f"Noise spectrum row {line_number} has an invalid frequency"
            )
        if not math.isfinite(density) or density < 0.0:
            raise ValueError(f"Noise spectrum row {line_number} has an invalid density")
        frequencies.append(frequency)
        densities.append(density)

    if len(frequencies) < 2:
        raise ValueError("Noise spectrum requires at least two numeric rows")

    frequency_array = np.asarray(frequencies, dtype=np.float64)
    density_array = np.asarray(densities, dtype=np.float64)
    order = np.argsort(frequency_array)
    frequency_array = frequency_array[order]
    density_array = density_array[order]
    unique_frequencies, inverse = np.unique(frequency_array, return_inverse=True)
    density_sums = np.zeros_like(unique_frequencies)
    counts = np.zeros_like(unique_frequencies)
    np.add.at(density_sums, inverse, density_array)
    np.add.at(counts, inverse, 1.0)
    if unique_frequencies.size < 2:
        raise ValueError("Noise spectrum requires at least two frequencies")
    return unique_frequencies, density_sums / counts


def equivalent_noise_charge(
    sensor_capacitance_pF: float,
    *,
    constant_electrons: float = 0.0,
    parallel_electrons: float = 0.0,
    slope_electrons_per_pF: float = 0.0,
) -> float:
    """Evaluate an ENC model in electrons."""
    values = (
        sensor_capacitance_pF,
        constant_electrons,
        parallel_electrons,
        slope_electrons_per_pF,
    )
    if any(value < 0.0 for value in values):
        raise ValueError("ENC inputs must be non-negative")
    series_electrons = slope_electrons_per_pF * sensor_capacitance_pF
    return math.sqrt(
        constant_electrons**2 + parallel_electrons**2 + series_electrons**2
    )


def enc_to_charge_fC(enc_electrons: float) -> float:
    """Convert equivalent noise charge from electrons to fC."""
    if enc_electrons < 0.0:
        raise ValueError("ENC must be non-negative")
    return enc_electrons * ELEMENTARY_CHARGE_C * 1.0e15


def output_noise_rms_from_enc(
    sensor_capacitance_pF: float,
    *,
    constant_electrons: float = 0.0,
    parallel_electrons: float = 0.0,
    slope_electrons_per_pF: float = 0.0,
    output_gain_mV_per_fC: float,
) -> tuple[float, float]:
    """Convert a capacitance-dependent ENC model to output RMS in mV."""
    if output_gain_mV_per_fC < 0.0:
        raise ValueError("Output charge gain must be non-negative")
    enc_electrons = equivalent_noise_charge(
        sensor_capacitance_pF,
        constant_electrons=constant_electrons,
        parallel_electrons=parallel_electrons,
        slope_electrons_per_pF=slope_electrons_per_pF,
    )
    return enc_to_charge_fC(enc_electrons) * output_gain_mV_per_fC, enc_electrons


def white_noise_spectrum_for_rms(
    rms: float,
    min_frequency_hz: float,
    max_frequency_hz: float,
) -> tuple[FloatArray, FloatArray]:
    """Build a flat amplitude spectral density with the requested RMS."""
    if rms < 0.0 or min_frequency_hz < 0.0:
        raise ValueError("Noise RMS and minimum frequency must be non-negative")
    if max_frequency_hz <= min_frequency_hz:
        raise ValueError("Maximum frequency must exceed minimum frequency")
    density = rms / math.sqrt(max_frequency_hz - min_frequency_hz)
    return (
        np.asarray([min_frequency_hz, max_frequency_hz], dtype=np.float64),
        np.asarray([density, density], dtype=np.float64),
    )


def spieler_noise_spectrum(
    sensor_capacitance_pF: float,
    *,
    voltage_noise_V_per_sqrtHz: float,
    current_noise_A_per_sqrtHz: float,
    flicker_voltage_noise_V2_Hz: float,
    transimpedance_ohm: float,
    min_frequency_hz: float,
    max_frequency_hz: float,
    points_per_decade: int = 100,
    pole_frequency_hz: float | None = None,
) -> tuple[FloatArray, FloatArray]:
    """Calculate the output ASD of an input-referred noise model."""
    non_negative = (
        sensor_capacitance_pF,
        voltage_noise_V_per_sqrtHz,
        current_noise_A_per_sqrtHz,
        flicker_voltage_noise_V2_Hz,
        transimpedance_ohm,
    )
    if any(value < 0.0 for value in non_negative):
        raise ValueError("Spieler noise inputs must be non-negative")
    if min_frequency_hz <= 0.0:
        raise ValueError("Minimum frequency must be positive")
    if max_frequency_hz <= min_frequency_hz:
        raise ValueError("Maximum frequency must exceed minimum frequency")
    if points_per_decade <= 0:
        raise ValueError("Points per decade must be positive")
    if pole_frequency_hz is not None and pole_frequency_hz <= 0.0:
        raise ValueError("Pole frequency must be positive")

    decades = math.log10(max_frequency_hz / min_frequency_hz)
    point_count = max(2, math.ceil(decades * points_per_decade) + 1)
    frequencies = np.logspace(
        math.log10(min_frequency_hz),
        math.log10(max_frequency_hz),
        point_count,
        dtype=np.float64,
    )
    capacitance_f = sensor_capacitance_pF * 1.0e-12
    angular_frequency = 2.0 * math.pi * frequencies
    voltage_psd = (
        voltage_noise_V_per_sqrtHz**2 + flicker_voltage_noise_V2_Hz / frequencies
    )
    current_psd = (
        current_noise_A_per_sqrtHz**2
        + np.square(angular_frequency * capacitance_f) * voltage_psd
    )
    transfer = np.full_like(frequencies, transimpedance_ohm)
    if pole_frequency_hz is not None:
        transfer /= np.sqrt(1.0 + np.square(frequencies / pole_frequency_hz))
    return frequencies, transfer * np.sqrt(current_psd)
