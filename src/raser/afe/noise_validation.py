#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

"""Validate noise spectra by resampling and comparing waveform statistics."""

import json
import os

import numpy as np

from .noise import estimate_noise_spectrum
from .noise import integrate_noise_spectrum_rms
from .noise import load_noise_spectrum
from .noise import synthesize_noise_from_spectrum
from .noise_estimation import collect_waveforms_from_root


def validate_waveforms(
    waveforms,
    time_step_s: float,
    *,
    segment_length=None,
    overlap: float = 0.5,
    window: str = "hann",
    n_synthetic: int = 64,
    seed: int = 12345,
) -> tuple[dict, tuple[np.ndarray, np.ndarray, np.ndarray]]:
    """Estimate a spectrum from measured waveforms and compare resampling."""
    measured = np.asarray(waveforms, dtype=np.float64)
    if measured.ndim == 1:
        measured = measured[np.newaxis, :]
    frequencies, measured_asd = estimate_noise_spectrum(
        measured,
        time_step_s,
        segment_length=segment_length,
        overlap=overlap,
        window=window,
        density_type="amplitude",
    )
    synthetic = _sample_waveforms(
        frequencies,
        measured_asd,
        measured.shape[1],
        time_step_s,
        n_synthetic,
        seed,
    )
    synthetic_freq, synthetic_asd = estimate_noise_spectrum(
        synthetic,
        time_step_s,
        segment_length=segment_length,
        overlap=overlap,
        window=window,
        density_type="amplitude",
    )
    metrics = _metrics(
        measured,
        synthetic,
        frequencies,
        measured_asd,
        synthetic_freq,
        synthetic_asd,
        time_step_s,
    )
    return metrics, _aligned_spectra(frequencies, measured_asd, synthetic_freq, synthetic_asd)


def validate_spectrum(
    frequencies,
    density,
    n_samples: int,
    time_step_s: float,
    *,
    density_type: str = "amplitude",
    unit_scale: float = 1.0,
    target_rms=None,
    min_frequency_hz=None,
    max_frequency_hz=None,
    segment_length=None,
    overlap: float = 0.5,
    window: str = "hann",
    n_synthetic: int = 64,
    seed: int = 12345,
) -> tuple[dict, tuple[np.ndarray, np.ndarray, np.ndarray]]:
    """Sample a configured spectrum and compare the estimated ASD to input."""
    frequencies = np.asarray(frequencies, dtype=np.float64)
    density = np.asarray(density, dtype=np.float64)
    configured_freq, configured_asd = _configured_asd(
        frequencies,
        density,
        density_type=density_type,
        unit_scale=unit_scale,
        target_rms=target_rms,
        min_frequency_hz=min_frequency_hz,
        max_frequency_hz=max_frequency_hz,
    )
    reference_freq, reference_asd = _cut_reference_asd(
        configured_freq,
        configured_asd,
        min_frequency_hz=min_frequency_hz,
        max_frequency_hz=max_frequency_hz,
    )

    synthetic = _sample_waveforms(
        configured_freq,
        configured_asd,
        n_samples,
        time_step_s,
        n_synthetic,
        seed,
        density_type="amplitude",
        min_frequency_hz=min_frequency_hz,
        max_frequency_hz=max_frequency_hz,
    )
    synthetic_freq, synthetic_asd = estimate_noise_spectrum(
        synthetic,
        time_step_s,
        segment_length=segment_length,
        overlap=overlap,
        window=window,
        density_type="amplitude",
    )
    metrics = _metrics(
        None,
        synthetic,
        reference_freq,
        reference_asd,
        synthetic_freq,
        synthetic_asd,
        time_step_s,
    )
    metrics["reference_rms"] = _sampled_reference_rms(
        configured_freq,
        configured_asd,
        n_samples,
        time_step_s,
        min_frequency_hz=min_frequency_hz,
        max_frequency_hz=max_frequency_hz,
    )
    metrics["continuous_reference_rms"] = integrate_noise_spectrum_rms(
        configured_freq,
        configured_asd,
        density_type="amplitude",
        min_frequency_hz=min_frequency_hz,
        max_frequency_hz=max_frequency_hz,
    )
    return metrics, _aligned_spectra(reference_freq, reference_asd, synthetic_freq, synthetic_asd)


def write_validation_report(path: str, metrics: dict) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w") as handle:
        json.dump(metrics, handle, indent=2)
        handle.write("\n")


def write_validation_spectrum_table(path: str, frequencies, reference_asd, synthetic_asd) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    frequencies = np.asarray(frequencies, dtype=np.float64)
    reference_asd = np.asarray(reference_asd, dtype=np.float64)
    synthetic_asd = np.asarray(synthetic_asd, dtype=np.float64)
    n = min(frequencies.size, reference_asd.size, synthetic_asd.size)
    with open(path, "w") as handle:
        handle.write("# frequency_hz reference_asd synthetic_asd ratio\n")
        for frequency, reference, synthetic in zip(
            frequencies[:n],
            reference_asd[:n],
            synthetic_asd[:n],
        ):
            ratio = synthetic / reference if reference != 0.0 else np.nan
            handle.write(
                f"{frequency:.8e} {reference:.8e} {synthetic:.8e} {ratio:.8e}\n"
            )


def save_validation_plot(path: str, frequencies, reference_asd, synthetic_asd) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    frequencies = np.asarray(frequencies, dtype=np.float64)
    reference_asd = np.asarray(reference_asd, dtype=np.float64)
    synthetic_asd = np.asarray(synthetic_asd, dtype=np.float64)
    n = min(frequencies.size, reference_asd.size, synthetic_asd.size)
    mask = (frequencies[:n] > 0.0) & (reference_asd[:n] > 0.0) & (synthetic_asd[:n] > 0.0)

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.loglog(frequencies[:n][mask], reference_asd[:n][mask], label="reference ASD")
    ax.loglog(frequencies[:n][mask], synthetic_asd[:n][mask], label="resampled ASD")
    ax.set_xlabel("Frequency [Hz]")
    ax.set_ylabel("ASD")
    ax.grid(True, which="both", alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def main(kwargs):
    output_dir = kwargs.get("output_dir") or "output/afe/noise_validation"
    os.makedirs(output_dir, exist_ok=True)
    report_path = kwargs.get("report") or os.path.join(output_dir, "noise_validation_metrics.json")
    plot_path = kwargs.get("plot") or os.path.join(output_dir, "noise_validation_asd.png")
    table_path = os.path.join(output_dir, "noise_validation_asd.txt")

    segment_length = kwargs.get("segment_length")
    overlap = kwargs.get("overlap")
    window = kwargs.get("window") or "hann"
    n_synthetic = kwargs.get("n_waveforms") or 64
    seed = kwargs.get("seed")
    if seed is None:
        seed = 12345

    input_file = kwargs.get("input_file")
    spectrum_file = kwargs.get("spectrum")
    if input_file:
        waveforms, time_step, sources = collect_waveforms_from_root(
            input_file,
            tree_name=kwargs.get("tree"),
            branches=kwargs.get("branches"),
            histograms=kwargs.get("histograms"),
            max_events=kwargs.get("max_events"),
        )
        if kwargs.get("time_step") is not None:
            time_step = float(kwargs["time_step"])
        metrics, spectra = validate_waveforms(
            waveforms,
            time_step,
            segment_length=segment_length,
            overlap=overlap,
            window=window,
            n_synthetic=n_synthetic,
            seed=seed,
        )
        metrics["mode"] = "waveforms"
        metrics["input_file"] = input_file
        metrics["waveform_sources"] = sources[:16]
        metrics["n_sources"] = len(sources)
    elif spectrum_file:
        if kwargs.get("time_step") is None or kwargs.get("n_samples") is None:
            raise ValueError("afe validate_noise --spectrum requires --time-step and --n-samples")
        frequencies, density = load_noise_spectrum(spectrum_file)
        metrics, spectra = validate_spectrum(
            frequencies,
            density,
            int(kwargs["n_samples"]),
            float(kwargs["time_step"]),
            density_type=kwargs.get("density_type") or "amplitude",
            unit_scale=kwargs.get("unit_scale") or 1.0,
            target_rms=kwargs.get("target_rms"),
            min_frequency_hz=kwargs.get("min_frequency"),
            max_frequency_hz=kwargs.get("max_frequency"),
            segment_length=segment_length,
            overlap=overlap,
            window=window,
            n_synthetic=n_synthetic,
            seed=seed,
        )
        metrics["mode"] = "spectrum"
        metrics["spectrum_file"] = spectrum_file
    else:
        raise ValueError("afe validate_noise requires either --input or --spectrum")

    metrics["report_path"] = report_path
    metrics["asd_table_path"] = table_path
    write_validation_spectrum_table(table_path, *spectra)
    try:
        save_validation_plot(plot_path, *spectra)
        metrics["plot_path"] = plot_path
    except ImportError as exc:
        metrics["plot_error"] = str(exc)
    write_validation_report(report_path, metrics)
    print(json.dumps(metrics, indent=2))
    print("Saved validation report to {}".format(report_path))
    print("Saved ASD comparison table to {}".format(table_path))
    if "plot_path" in metrics:
        print("Saved ASD comparison plot to {}".format(plot_path))


def _sample_waveforms(
    frequencies,
    density,
    n_samples: int,
    time_step_s: float,
    n_waveforms: int,
    seed: int,
    *,
    density_type: str = "amplitude",
    min_frequency_hz=None,
    max_frequency_hz=None,
) -> np.ndarray:
    n_waveforms = int(n_waveforms)
    if n_waveforms < 1:
        raise ValueError("n_waveforms must be positive")
    return np.vstack([
        synthesize_noise_from_spectrum(
            frequencies,
            density,
            n_samples,
            time_step_s,
            seed=seed + index,
            density_type=density_type,
            min_frequency_hz=min_frequency_hz,
            max_frequency_hz=max_frequency_hz,
        )
        for index in range(n_waveforms)
    ])


def _configured_asd(
    frequencies,
    density,
    *,
    density_type: str,
    unit_scale: float,
    target_rms,
    min_frequency_hz,
    max_frequency_hz,
) -> tuple[np.ndarray, np.ndarray]:
    density_key = density_type.lower()
    scale = float(unit_scale)
    if density_key in ("power", "psd"):
        psd = density * scale * scale
    elif density_key in ("amplitude", "asd", "sqrt_psd", "sqrt"):
        psd = np.square(density * scale)
    else:
        raise ValueError(f"Unsupported density_type: {density_type}")

    mask = np.isfinite(frequencies) & np.isfinite(psd) & (frequencies >= 0.0) & (psd >= 0.0)
    frequencies = frequencies[mask]
    psd = psd[mask]
    if frequencies.size < 2:
        raise ValueError("configured spectrum has fewer than two valid points")

    order = np.argsort(frequencies)
    frequencies = frequencies[order]
    psd = psd[order]

    if target_rms is not None:
        rms = integrate_noise_spectrum_rms(
            frequencies,
            np.sqrt(psd),
            density_type="amplitude",
            min_frequency_hz=min_frequency_hz,
            max_frequency_hz=max_frequency_hz,
        )
        target_rms = float(target_rms)
        if target_rms < 0.0:
            raise ValueError("target_rms must be non-negative")
        if rms > 0.0:
            psd *= (target_rms / rms) ** 2
        elif target_rms > 0.0:
            raise ValueError("cannot normalize zero-RMS spectrum")

    return frequencies, np.sqrt(psd)


def _cut_reference_asd(
    frequencies,
    reference_asd,
    *,
    min_frequency_hz,
    max_frequency_hz,
) -> tuple[np.ndarray, np.ndarray]:
    mask = np.isfinite(frequencies) & np.isfinite(reference_asd)
    mask &= (frequencies >= 0.0) & (reference_asd >= 0.0)
    frequencies = frequencies[mask]
    reference_asd = reference_asd[mask]
    if frequencies.size < 2:
        raise ValueError("configured spectrum has fewer than two points in the requested frequency range")

    order = np.argsort(frequencies)
    frequencies = frequencies[order]
    reference_asd = reference_asd[order]

    lower = frequencies[0]
    upper = frequencies[-1]
    if min_frequency_hz is not None:
        lower = max(lower, float(min_frequency_hz))
    if max_frequency_hz is not None:
        upper = min(upper, float(max_frequency_hz))
    if upper <= lower:
        raise ValueError("configured spectrum has fewer than two points in the requested frequency range")

    keep = (frequencies >= lower) & (frequencies <= upper)
    cut_frequencies = frequencies[keep]
    cut_asd = reference_asd[keep]

    if cut_frequencies.size == 0 or cut_frequencies[0] > lower:
        cut_frequencies = np.insert(cut_frequencies, 0, lower)
        cut_asd = np.insert(cut_asd, 0, np.interp(lower, frequencies, reference_asd))
    if cut_frequencies[-1] < upper:
        cut_frequencies = np.append(cut_frequencies, upper)
        cut_asd = np.append(cut_asd, np.interp(upper, frequencies, reference_asd))

    return cut_frequencies, cut_asd


def _sampled_reference_rms(
    frequencies,
    reference_asd,
    n_samples: int,
    time_step_s: float,
    *,
    min_frequency_hz=None,
    max_frequency_hz=None,
) -> float:
    fft_frequencies = np.fft.rfftfreq(int(n_samples), d=float(time_step_s))
    density_grid = np.interp(
        fft_frequencies,
        frequencies,
        reference_asd,
        left=0.0,
        right=0.0,
    )
    psd_grid = np.square(density_grid)
    if min_frequency_hz is not None:
        psd_grid = np.where(fft_frequencies >= float(min_frequency_hz), psd_grid, 0.0)
    if max_frequency_hz is not None:
        psd_grid = np.where(fft_frequencies <= float(max_frequency_hz), psd_grid, 0.0)
    if psd_grid.size > 0:
        psd_grid[0] = 0.0
    df = 1.0 / (int(n_samples) * float(time_step_s))
    return float(np.sqrt(np.sum(psd_grid) * df))


def _aligned_spectra(reference_freq, reference_asd, synthetic_freq, synthetic_asd):
    reference_on_synthetic = np.interp(
        synthetic_freq,
        reference_freq,
        reference_asd,
        left=np.nan,
        right=np.nan,
    )
    mask = (
        np.isfinite(reference_on_synthetic)
        & np.isfinite(synthetic_asd)
        & (synthetic_freq >= 0.0)
    )
    return synthetic_freq[mask], reference_on_synthetic[mask], synthetic_asd[mask]


def _metrics(
    measured,
    synthetic,
    reference_freq,
    reference_asd,
    synthetic_freq,
    synthetic_asd,
    time_step_s: float,
) -> dict:
    reference_on_synthetic = np.interp(
        synthetic_freq,
        reference_freq,
        reference_asd,
        left=np.nan,
        right=np.nan,
    )
    mask = (
        (synthetic_freq > 0.0)
        & np.isfinite(reference_on_synthetic)
        & (reference_on_synthetic > 0.0)
        & (synthetic_asd > 0.0)
    )
    log_ratio = np.log10(synthetic_asd[mask] / reference_on_synthetic[mask])
    if log_ratio.size == 0:
        raise ValueError("reference and synthetic spectra do not overlap")

    synthetic_rms = _waveform_rms(synthetic)
    metrics = {
        "n_synthetic_waveforms": int(synthetic.shape[0]),
        "n_samples": int(synthetic.shape[1]),
        "time_step_s": float(time_step_s),
        "synthetic_rms_mean": float(np.mean(synthetic_rms)),
        "synthetic_rms_std": float(np.std(synthetic_rms)),
        "asd_log10_ratio_mean": float(np.mean(log_ratio)),
        "asd_log10_ratio_rms": float(np.sqrt(np.mean(np.square(log_ratio)))),
        "asd_ratio_median": float(np.median(np.power(10.0, log_ratio))),
        "synthetic_tail_gt_3sigma": _tail_fraction(synthetic),
    }
    if measured is not None:
        measured_rms = _waveform_rms(measured)
        measured_rms_mean = float(np.mean(measured_rms))
        metrics.update({
            "n_measured_waveforms": int(measured.shape[0]),
            "measured_rms_mean": measured_rms_mean,
            "measured_rms_std": float(np.std(measured_rms)),
            "rms_relative_difference": float(
                (np.mean(synthetic_rms) - measured_rms_mean) / measured_rms_mean
            ) if measured_rms_mean != 0.0 else None,
            "measured_tail_gt_3sigma": _tail_fraction(measured),
        })
    return metrics


def _waveform_rms(waveforms) -> np.ndarray:
    centered = waveforms - np.mean(waveforms, axis=1, keepdims=True)
    return np.std(centered, axis=1)


def _tail_fraction(waveforms) -> float:
    centered = waveforms - np.mean(waveforms, axis=1, keepdims=True)
    rms = np.std(centered, axis=1, keepdims=True)
    valid = rms[:, 0] > 0.0
    if not np.any(valid):
        return 0.0
    normalized = np.abs(centered[valid] / rms[valid])
    return float(np.mean(normalized > 3.0))
