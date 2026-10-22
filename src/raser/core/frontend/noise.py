"""Frontend noise spectra and time-domain synthesis."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any
from typing import Literal
from typing import TypeAlias
from typing import cast

import numpy as np
from numpy.typing import NDArray


ELEMENTARY_CHARGE_C = 1.602176634e-19
DensityType = Literal["amplitude", "power"]
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


def synthesize_noise_from_spectrum(
    frequencies_hz: FloatArray,
    spectral_density: FloatArray,
    n_samples: int,
    time_step_s: float,
    *,
    seed: int | None = None,
    density_type: DensityType = "amplitude",
    unit_scale: float = 1.0,
    mean: float = 0.0,
    target_rms: float | None = None,
    min_frequency_hz: float | None = None,
    max_frequency_hz: float | None = None,
    randomize_amplitude: bool = True,
) -> FloatArray:
    """Generate a real waveform from a one-sided ASD or PSD."""
    if n_samples <= 0 or time_step_s <= 0.0:
        raise ValueError("Sample count and time step must be positive")
    frequencies = np.asarray(frequencies_hz, dtype=np.float64)
    densities = np.asarray(spectral_density, dtype=np.float64)
    if frequencies.ndim != 1 or densities.ndim != 1:
        raise ValueError("Noise spectrum arrays must be one-dimensional")
    if frequencies.size != densities.size or frequencies.size < 2:
        raise ValueError("Noise spectrum arrays must have equal usable lengths")
    if not np.all(np.isfinite(frequencies)) or not np.all(np.isfinite(densities)):
        raise ValueError("Noise spectrum values must be finite")
    if np.any(frequencies < 0.0) or np.any(densities < 0.0):
        raise ValueError("Noise spectrum values must be non-negative")
    if np.any(np.diff(frequencies) <= 0.0):
        raise ValueError("Noise spectrum frequencies must increase")
    if unit_scale < 0.0:
        raise ValueError("Noise spectrum unit scale must be non-negative")

    fft_frequencies = np.fft.rfftfreq(n_samples, d=time_step_s)
    density_grid = np.interp(
        fft_frequencies,
        frequencies,
        densities,
        left=0.0,
        right=0.0,
    )
    if density_type == "amplitude":
        psd_grid = np.square(density_grid * unit_scale)
    elif density_type == "power":
        psd_grid = density_grid * unit_scale**2
    else:
        raise ValueError(f"Unsupported density type: {density_type}")

    if min_frequency_hz is not None:
        if min_frequency_hz < 0.0:
            raise ValueError("Minimum frequency must be non-negative")
        psd_grid = np.where(fft_frequencies >= min_frequency_hz, psd_grid, 0.0)
    if max_frequency_hz is not None:
        if max_frequency_hz <= 0.0:
            raise ValueError("Maximum frequency must be positive")
        psd_grid = np.where(fft_frequencies <= max_frequency_hz, psd_grid, 0.0)

    rng = np.random.default_rng(seed)
    spectrum = np.zeros(fft_frequencies.shape, dtype=np.complex128)
    frequency_step = 1.0 / (n_samples * time_step_s)
    interior = np.arange(
        1,
        len(fft_frequencies) - (1 if n_samples % 2 == 0 else 0),
    )
    if interior.size:
        if randomize_amplitude:
            sigma = n_samples * np.sqrt(psd_grid[interior] * frequency_step) / 2.0
            spectrum[interior] = rng.normal(0.0, sigma) + 1j * rng.normal(0.0, sigma)
        else:
            amplitude = n_samples * np.sqrt(psd_grid[interior] * frequency_step / 2.0)
            phase = rng.uniform(0.0, 2.0 * math.pi, size=interior.size)
            spectrum[interior] = amplitude * np.exp(1j * phase)
    if n_samples % 2 == 0:
        nyquist = len(fft_frequencies) - 1
        amplitude = n_samples * math.sqrt(psd_grid[nyquist] * frequency_step)
        spectrum[nyquist] = (
            rng.normal(0.0, amplitude)
            if randomize_amplitude
            else amplitude * rng.choice((-1.0, 1.0))
        )

    noise = np.asarray(np.fft.irfft(spectrum, n=n_samples), dtype=np.float64)
    noise -= np.mean(noise)
    if target_rms is not None:
        if target_rms < 0.0:
            raise ValueError("Target RMS must be non-negative")
        current_rms = float(np.std(noise))
        if target_rms == 0.0:
            noise.fill(0.0)
        elif current_rms == 0.0:
            raise ValueError("Noise spectrum yields zero RMS")
        else:
            noise *= target_rms / current_rms
    noise += mean
    return noise


def synthesize_noise_from_config(
    noise_spectrum,
    n_samples: int,
    time_step_s: float,
    *,
    base_dir: str | Path | None = None,
    sensor_capacitance_pF: float | None = None,
    seed: int | None = None,
    mean: float = 0.0,
    target_rms: float | None = None,
):
    """Resolve a Frontend noise definition and synthesize one waveform."""
    config: dict[str, Any] = (
        {"file": noise_spectrum}
        if isinstance(noise_spectrum, (str, Path))
        else dict(noise_spectrum)
    )
    model = str(config.get("model", "")).lower()
    spectrum_file = config.get("file") or config.get("path")
    if model == "spieler":
        if sensor_capacitance_pF is None:
            raise ValueError("Spieler noise requires Device capacitance")
        frequencies, density = spieler_noise_spectrum(
            float(sensor_capacitance_pF),
            voltage_noise_V_per_sqrtHz=float(
                config.get("voltage_noise_V_per_sqrtHz", 0.0)
            )
            + float(config.get("voltage_noise_nV_per_sqrtHz", 0.0)) * 1.0e-9,
            current_noise_A_per_sqrtHz=float(
                config.get("current_noise_A_per_sqrtHz", 0.0)
            )
            + float(config.get("current_noise_fA_per_sqrtHz", 0.0)) * 1.0e-15,
            flicker_voltage_noise_V2_Hz=float(
                config.get("flicker_voltage_noise_V2_Hz", 0.0)
            )
            + float(config.get("flicker_voltage_noise_nV2_Hz", 0.0)) * 1.0e-18,
            transimpedance_ohm=float(config["transimpedance_ohm"]),
            min_frequency_hz=float(config.get("min_frequency_hz", 1.0)),
            max_frequency_hz=float(config.get("max_frequency_hz", 1.0e9)),
            points_per_decade=int(config.get("points_per_decade", 100)),
            pole_frequency_hz=(
                float(config["pole_frequency_hz"])
                if config.get("pole_frequency_hz") is not None
                else None
            ),
        )
    elif spectrum_file is not None:
        path = Path(spectrum_file).expanduser()
        if not path.is_absolute() and base_dir is not None:
            path = Path(base_dir) / path
        frequencies, density = load_noise_spectrum(path)
    else:
        raise ValueError("Noise definition requires a model or spectrum file")

    density_type = str(config.get("density_type", "amplitude"))
    if density_type not in {"amplitude", "power"}:
        raise ValueError(f"Unsupported density type: {density_type}")
    noise = synthesize_noise_from_spectrum(
        frequencies,
        density,
        n_samples,
        time_step_s,
        seed=seed,
        density_type=cast(DensityType, density_type),
        unit_scale=float(config.get("unit_scale", 1.0)),
        mean=mean,
        target_rms=(
            float(config["target_rms"])
            if config.get("target_rms") is not None
            else target_rms
        ),
        min_frequency_hz=(
            float(config["min_frequency_hz"])
            if config.get("min_frequency_hz") is not None
            else None
        ),
        max_frequency_hz=(
            float(config["max_frequency_hz"])
            if config.get("max_frequency_hz") is not None
            else None
        ),
        randomize_amplitude=bool(config.get("randomize_amplitude", True)),
    )
    return noise, frequencies, density
