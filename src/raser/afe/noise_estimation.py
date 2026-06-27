#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

"""Estimate electronics noise spectra from baseline ROOT waveforms."""

import json
import os
import subprocess
import time
from typing import Optional

import numpy as np

from .noise import estimate_noise_spectrum
from .noise import integrate_noise_spectrum_rms
from .noise import load_noise_spectrum
from .noise import write_noise_spectrum
from .ngspice import set_tmp_noise_cir


SPICE_NOISE_LABELS = (
    "estimate_spice_noise",
    "estimate_spice_noise_spectrum",
    "spice_noise",
    "spice_noise_spectrum",
)


def histogram_to_samples(histogram) -> tuple[np.ndarray, float]:
    """Convert a ROOT TH1 waveform to samples and bin width."""
    n_bins = histogram.GetNbinsX()
    if n_bins < 2:
        raise ValueError("histogram must have at least two bins")
    samples = np.asarray(
        [histogram.GetBinContent(index) for index in range(1, n_bins + 1)],
        dtype=np.float64,
    )
    return samples, float(histogram.GetBinWidth(1))


def collect_waveforms_from_root(
    path: str,
    *,
    tree_name: Optional[str] = "tree",
    branches: Optional[list[str]] = None,
    histograms: Optional[list[str]] = None,
    max_events: Optional[int] = None,
) -> tuple[np.ndarray, float, list[str]]:
    """Load baseline/no-signal waveforms from a ROOT file.

    If ``histograms`` is supplied, those top-level or path-addressed TH1
    objects are used. Otherwise, TH1 branches from ``tree_name`` are used when
    available. For single-waveform ROOT files, a top-level ``electronics_mV``
    histogram is preferred.
    """
    import ROOT

    root_file = ROOT.TFile.Open(path)
    if not root_file or root_file.IsZombie():
        raise OSError(f"Cannot open ROOT file: {path}")

    try:
        waveforms = []
        time_steps = []
        sources = []
        explicit_sources = bool(histograms or branches)

        if histograms:
            for name in histograms:
                histogram = root_file.Get(name)
                if not histogram:
                    raise KeyError(f"Histogram not found in {path}: {name}")
                samples, time_step = histogram_to_samples(histogram)
                waveforms.append(samples)
                time_steps.append(time_step)
                sources.append(name)
        else:
            tree_name = _normalized_tree_name(tree_name)
            tree = root_file.Get(tree_name) if tree_name else None
            if tree is None and branches:
                raise KeyError(f"TTree not found in {path}: {tree_name}")
            if tree:
                branch_names = branches or _histogram_branch_names(tree)
                _collect_tree_histograms(
                    tree,
                    branch_names,
                    waveforms,
                    time_steps,
                    sources,
                    max_events=max_events,
                )

            if not waveforms and not branches:
                preferred = root_file.Get("electronics_mV")
                if preferred:
                    samples, time_step = histogram_to_samples(preferred)
                    waveforms.append(samples)
                    time_steps.append(time_step)
                    sources.append("electronics_mV")
                else:
                    _collect_directory_histograms(
                        root_file,
                        "",
                        waveforms,
                        time_steps,
                        sources,
                    )

        if not waveforms:
            raise ValueError(f"No ROOT TH1 waveforms found in {path}")

        if not explicit_sources:
            waveforms, time_steps, sources = _select_auto_waveforms(
                waveforms,
                time_steps,
                sources,
            )

        waveform_length = len(waveforms[0])
        if any(len(waveform) != waveform_length for waveform in waveforms):
            raise ValueError("all noise waveforms must have the same number of bins")

        time_step = time_steps[0]
        if any(abs(step - time_step) > max(abs(time_step), 1.0) * 1.0e-12 for step in time_steps):
            raise ValueError("all noise waveforms must have the same bin width")

        return np.vstack(waveforms), time_step, sources
    finally:
        root_file.Close()


def build_noise_spectrum_config(
    spectrum_path: str,
    *,
    density_type: str,
    unit_scale: float = 1.0,
    target_rms: Optional[float] = None,
    min_frequency_hz: Optional[float] = None,
    max_frequency_hz: Optional[float] = None,
    config_dir: Optional[str] = None,
) -> dict:
    """Build a sidecar config consumed by Amplifier spectral-noise loading."""
    spectrum_ref = _spectrum_config_reference(spectrum_path, config_dir)
    config = {
        "file": spectrum_ref,
        "density_type": density_type,
        "unit_scale": float(unit_scale),
        "randomize_amplitude": True,
    }
    if target_rms is not None:
        config["target_rms"] = float(target_rms)
    if min_frequency_hz is not None:
        config["min_frequency_hz"] = float(min_frequency_hz)
    if max_frequency_hz is not None:
        config["max_frequency_hz"] = float(max_frequency_hz)
    return config


def write_noise_config(path: str, config: dict) -> None:
    with open(path, "w") as handle:
        json.dump(config, handle, indent=4)
        handle.write("\n")


def main(kwargs):
    if kwargs.get("label") in SPICE_NOISE_LABELS or kwargs.get("spice_circuit"):
        main_spice(kwargs)
        return

    input_file = kwargs.get("input_file")
    if not input_file:
        raise ValueError("afe estimate_noise requires --input baseline ROOT file")

    electronics_name = kwargs["name"]
    setting_path = os.getenv("RASER_SETTING_PATH", "setting")
    electronics_dir = os.path.join(setting_path, "electronics")
    os.makedirs(electronics_dir, exist_ok=True)

    output_path = kwargs.get("output")
    if output_path is None:
        output_path = os.path.join(
            electronics_dir,
            f"{electronics_name}_estimated_noise_spectrum.raw",
        )
    output_path = os.path.abspath(output_path)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    config_path = kwargs.get("config_output")
    if config_path is None:
        config_path = os.path.join(electronics_dir, f"{electronics_name}.noise.json")
    config_path = os.path.abspath(config_path)
    os.makedirs(os.path.dirname(config_path), exist_ok=True)

    waveforms, inferred_time_step, sources = collect_waveforms_from_root(
        input_file,
        tree_name=kwargs.get("tree"),
        branches=kwargs.get("branches"),
        histograms=kwargs.get("histograms"),
        max_events=kwargs.get("max_events"),
    )
    time_step = kwargs.get("time_step") or inferred_time_step
    density_type = kwargs.get("density_type") or "amplitude"
    unit_scale = kwargs.get("unit_scale")
    if unit_scale is None:
        unit_scale = 1.0

    frequencies, density = estimate_noise_spectrum(
        waveforms,
        time_step,
        segment_length=kwargs.get("segment_length"),
        overlap=kwargs.get("overlap"),
        window=kwargs.get("window") or "hann",
        density_type=density_type,
        min_frequency_hz=kwargs.get("min_frequency"),
        max_frequency_hz=kwargs.get("max_frequency"),
    )
    write_noise_spectrum(output_path, frequencies, density)

    config = build_noise_spectrum_config(
        output_path,
        density_type=density_type,
        unit_scale=unit_scale,
        target_rms=kwargs.get("target_rms"),
        min_frequency_hz=kwargs.get("min_frequency"),
        max_frequency_hz=kwargs.get("max_frequency"),
        config_dir=os.path.dirname(config_path),
    )
    write_noise_config(config_path, config)

    print("Estimated noise spectrum from {} waveform(s).".format(waveforms.shape[0]))
    print("Input ROOT file: {}".format(input_file))
    print("Waveform sources: {}".format(", ".join(sources[:8])))
    if len(sources) > 8:
        print("Additional sources: {}".format(len(sources) - 8))
    print("Time step [s]: {:.8e}".format(float(time_step)))
    print("Spectrum file: {}".format(output_path))
    print("Noise config: {}".format(config_path))


def main_spice(kwargs):
    electronics_name = kwargs["name"]
    setting_path = os.getenv("RASER_SETTING_PATH", "setting")
    electronics_dir = os.path.join(setting_path, "electronics")
    os.makedirs(electronics_dir, exist_ok=True)

    circuit_path = kwargs.get("spice_circuit")
    if circuit_path is None:
        circuit_path = os.path.join(electronics_dir, f"{electronics_name}.cir")
    circuit_path = os.path.abspath(circuit_path)
    if not os.path.exists(circuit_path):
        raise OSError(f"SPICE circuit file not found: {circuit_path}")

    output_path = kwargs.get("output")
    if output_path is None:
        output_path = os.path.join(electronics_dir, f"{electronics_name}_onoise_spectrum.raw")
    output_path = os.path.abspath(output_path)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    config_path = kwargs.get("config_output")
    if config_path is None:
        config_path = os.path.join(electronics_dir, f"{electronics_name}.noise.json")
    config_path = os.path.abspath(config_path)
    os.makedirs(os.path.dirname(config_path), exist_ok=True)

    density_type = kwargs.get("density_type") or "amplitude"
    unit_scale = kwargs.get("unit_scale")
    if unit_scale is None:
        unit_scale = 1000.0

    work_dir = os.path.join("output", "afe", electronics_name)
    os.makedirs(work_dir, exist_ok=True)
    frequencies, density, return_code = estimate_spice_noise_spectrum(
        circuit_path,
        output_path,
        density_type=density_type,
        ngspice_executable=kwargs.get("ngspice") or "ngspice",
        work_dir=work_dir,
    )

    config = build_noise_spectrum_config(
        output_path,
        density_type=density_type,
        unit_scale=unit_scale,
        target_rms=kwargs.get("target_rms"),
        min_frequency_hz=kwargs.get("min_frequency"),
        max_frequency_hz=kwargs.get("max_frequency"),
        config_dir=os.path.dirname(config_path),
    )
    write_noise_config(config_path, config)

    configured_rms = integrate_noise_spectrum_rms(
        frequencies,
        density,
        density_type=density_type,
        unit_scale=unit_scale,
        min_frequency_hz=kwargs.get("min_frequency"),
        max_frequency_hz=kwargs.get("max_frequency"),
    )

    print("Estimated noise spectrum from SPICE .noise.")
    print("Circuit file: {}".format(circuit_path))
    if return_code != 0:
        print("Warning: ngspice exited with code {} but produced a usable spectrum.".format(return_code))
    print("Spectrum file: {}".format(output_path))
    print("Noise config: {}".format(config_path))
    print("Configured RMS after unit/frequency cuts: {:.8e}".format(configured_rms))


def estimate_spice_noise_spectrum(
    circuit_path: str,
    output_path: str,
    *,
    density_type: str = "amplitude",
    ngspice_executable: str = "ngspice",
    work_dir: Optional[str] = None,
) -> tuple[np.ndarray, np.ndarray, int]:
    """Run ngspice .noise and write a normalized two-column spectrum."""
    if work_dir is None:
        work_dir = os.path.dirname(os.path.abspath(output_path))
    os.makedirs(work_dir, exist_ok=True)
    label = "spice_noise_{}_{}".format(os.getpid(), time.time_ns())
    tmp_cir, noise_raw = set_tmp_noise_cir(work_dir, circuit_path, label)
    if tmp_cir is None:
        raise ValueError(
            "SPICE circuit must contain an active .noise command and "
            "wrdata ... onoise_spectrum"
        )

    try:
        completed = subprocess.run(
            [ngspice_executable, "-b", tmp_cir],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if not os.path.exists(noise_raw) or os.path.getsize(noise_raw) == 0:
            raise RuntimeError(
                "ngspice did not produce a usable noise spectrum.\n"
                + _subprocess_tail(completed)
            )

        frequencies, density = load_noise_spectrum(noise_raw)
        density_key = density_type.lower()
        if density_key in ("power", "psd"):
            density = np.square(density)
        elif density_key not in ("amplitude", "asd", "sqrt_psd", "sqrt"):
            raise ValueError(f"Unsupported density_type: {density_type}")

        write_noise_spectrum(output_path, frequencies, density)
        return frequencies, density, completed.returncode
    finally:
        _remove_if_exists(tmp_cir)
        _remove_if_exists(noise_raw)


def _subprocess_tail(completed) -> str:
    stdout = (completed.stdout or "").strip().splitlines()
    stderr = (completed.stderr or "").strip().splitlines()
    lines = []
    if stdout:
        lines.append("stdout tail:")
        lines.extend(stdout[-12:])
    if stderr:
        lines.append("stderr tail:")
        lines.extend(stderr[-12:])
    return "\n".join(lines)


def _remove_if_exists(path: Optional[str]) -> None:
    if path and os.path.exists(path):
        os.remove(path)


def _histogram_branch_names(tree) -> list[str]:
    branch_names = []
    for branch in tree.GetListOfBranches():
        class_name = branch.GetClassName()
        if class_name and class_name.startswith("TH1"):
            branch_names.append(branch.GetName())
    return branch_names


def _normalized_tree_name(tree_name: Optional[str]) -> Optional[str]:
    if tree_name is None:
        return None
    key = str(tree_name).strip()
    if key.lower() in ("", "none", "null", "false", "0", "-"):
        return None
    return key


def _spectrum_config_reference(spectrum_path: str, config_dir: Optional[str]) -> str:
    spectrum_path = os.path.abspath(spectrum_path)
    if config_dir is None:
        return os.path.basename(spectrum_path)
    config_dir = os.path.abspath(config_dir)
    try:
        return os.path.relpath(spectrum_path, config_dir)
    except ValueError:
        return spectrum_path


def _is_th1_waveform(obj) -> bool:
    class_name = obj.ClassName()
    return class_name.startswith("TH1")


def _select_auto_waveforms(waveforms, time_steps, sources):
    candidates = [
        (waveform, time_step, source)
        for waveform, time_step, source in zip(waveforms, time_steps, sources)
        if not _is_frame_source(source)
    ]
    if not candidates:
        candidates = list(zip(waveforms, time_steps, sources))

    preferred = [
        candidate
        for candidate in candidates
        if _is_preferred_waveform_source(candidate[2])
    ]
    if preferred:
        candidates = preferred

    lengths = {}
    for candidate in candidates:
        lengths.setdefault(len(candidate[0]), []).append(candidate)
    selected = max(lengths.values(), key=lambda group: (len(group), len(group[0][0])))
    selected_waveforms, selected_time_steps, selected_sources = zip(*selected)
    return list(selected_waveforms), list(selected_time_steps), list(selected_sources)


def _is_frame_source(source: str) -> bool:
    leaf = os.path.basename(source).lower()
    return leaf in ("hframe", "frame") or leaf.startswith("hframe_")


def _is_preferred_waveform_source(source: str) -> bool:
    key = source.lower()
    return any(
        token in key
        for token in ("electronics", "amplified_waveform", "baseline", "noise", "waveform")
    )


def _collect_tree_histograms(
    tree,
    branch_names: list[str],
    waveforms: list[np.ndarray],
    time_steps: list[float],
    sources: list[str],
    *,
    max_events: Optional[int],
) -> None:
    if not branch_names:
        return
    n_entries = tree.GetEntries()
    if max_events is not None:
        max_events = int(max_events)
        if max_events < 1:
            raise ValueError("max_events must be positive")
        n_entries = min(n_entries, max_events)
    for entry in range(n_entries):
        tree.GetEntry(entry)
        for branch_name in branch_names:
            histogram = getattr(tree, branch_name, None)
            if histogram is None:
                raise KeyError(f"Tree branch not found: {branch_name}")
            samples, time_step = histogram_to_samples(histogram)
            waveforms.append(samples)
            time_steps.append(time_step)
            sources.append(f"{tree.GetName()}.{branch_name}[{entry}]")


def _collect_directory_histograms(
    directory,
    prefix: str,
    waveforms: list[np.ndarray],
    time_steps: list[float],
    sources: list[str],
) -> None:
    for key in directory.GetListOfKeys():
        obj = key.ReadObj()
        name = key.GetName()
        full_name = f"{prefix}/{name}" if prefix else name
        _collect_object_histograms(obj, full_name, waveforms, time_steps, sources)


def _collect_object_histograms(
    obj,
    name: str,
    waveforms: list[np.ndarray],
    time_steps: list[float],
    sources: list[str],
) -> None:
    if obj.InheritsFrom("TDirectory"):
        _collect_directory_histograms(obj, name, waveforms, time_steps, sources)
        return

    if _is_th1_waveform(obj):
        samples, time_step = histogram_to_samples(obj)
        waveforms.append(samples)
        time_steps.append(time_step)
        sources.append(name)
        return

    primitives = obj.GetListOfPrimitives() if hasattr(obj, "GetListOfPrimitives") else None
    if not primitives:
        return
    for child in primitives:
        child_name = f"{name}/{child.GetName()}"
        _collect_object_histograms(child, child_name, waveforms, time_steps, sources)
