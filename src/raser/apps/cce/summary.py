"""CCE summary analysis."""

import json
from pathlib import Path

import numpy as np
import ROOT

from raser.core.metrics import waveform_stats
from raser.supports.output import create_path
from raser.supports import runs


MEASURED_COLUMNS = {
    "amplified_amplitude",
    "amplified_charge",
    "amplified_ToA",
    "amplified_ToT",
    "amplified_CFD50",
}
TRUTH_COLUMNS = {
    "e_dep",
    "generated_pairs",
    "generated_charge",
    "par_in_x",
    "par_in_y",
    "par_in_z",
    "par_out_x",
    "par_out_y",
    "par_out_z",
}
RUN_COLUMNS = {"voltage", "irradiation_flux"}


def _run_root(kwargs):
    run_id = kwargs.get("run")
    source = kwargs.get("source")
    voltage = kwargs.get("voltage")
    field = kwargs.get("field")
    if run_id == "latest":
        return runs.latest_run_path("cce", source=source, voltage=voltage, field=field)
    path = Path(str(run_id))
    if path.is_absolute() or len(path.parts) > 1:
        return path
    return runs.run_path("cce", str(run_id))


def _read_event_arrays(batch_path):
    event_files = sorted(batch_path.glob("stats_*.root"))
    if not event_files:
        raise FileNotFoundError(f"No CCE ROOT statistics files found in {batch_path}")

    columns = {}
    for event_file in event_files:
        root_file = ROOT.TFile.Open(str(event_file))
        if root_file is None or root_file.IsZombie():
            raise OSError(f"Cannot open CCE ROOT statistics file {event_file}")
        event_tree = root_file.Get("events")
        if event_tree is None:
            root_file.Close()
            raise ValueError(f"Missing events TTree in {event_file}")
        names = [branch.GetName() for branch in event_tree.GetListOfBranches()]
        if not columns:
            columns = {name: [] for name in names}
        missing = set(columns) - set(names)
        extra = set(names) - set(columns)
        if missing or extra:
            root_file.Close()
            raise ValueError(
                f"CCE event statistics schema mismatch in {event_file}: "
                f"missing={sorted(missing)}, extra={sorted(extra)}"
            )
        for entry in event_tree:
            for name in columns:
                columns[name].append(float(getattr(entry, name)))
        root_file.Close()
    return {name: np.asarray(values, dtype=np.float64) for name, values in columns.items()}


def _column(columns, name):
    return columns[name]


def _stats(values):
    values = values[np.isfinite(values)]
    if values.size == 0:
        return {
            "count": 0,
            "mean": None,
            "std": None,
            "min": None,
            "max": None,
        }
    return {
        "count": int(values.size),
        "mean": float(np.mean(values)),
        "std": float(np.std(values)),
        "min": float(np.min(values)),
        "max": float(np.max(values)),
    }


def _summary(columns):
    names = columns.keys()
    result = {
        "events": int(len(_column(columns, "event"))),
        "measured": {},
        "truth": {},
        "intermediate": {},
        "run": {},
    }
    for name in names:
        if name == "event":
            continue
        values = _column(columns, name)
        if name in MEASURED_COLUMNS or name.startswith("amplified_"):
            group = "measured"
        elif name in TRUTH_COLUMNS:
            group = "truth"
        elif name in RUN_COLUMNS:
            group = "run"
        else:
            group = "intermediate"
        result[group][name] = _stats(values)
    return result


class _WaveformStatsDraw:
    def __init__(self, output_path):
        self.output_path = str(output_path)


def _has_distribution(values):
    values = [value for value in values if np.isfinite(value)]
    return len(values) > 0 and min(values) != max(values)


def _plot_with_existing_functions(columns, output_path):
    drawer = _WaveformStatsDraw(output_path)
    measured_tag = "cce_measured"
    truth_tag = "cce_truth"
    amplified_charge = list(_column(columns, "amplified_charge"))
    amplified_amplitude = list(_column(columns, "amplified_amplitude"))
    generated_charge = list(_column(columns, "generated_charge") * 1.0e15)
    e_dep = list(_column(columns, "e_dep"))

    written = []
    if _has_distribution(amplified_charge):
        waveform_stats.WaveformStatistics.amplitude_fit(
            drawer,
            amplified_charge,
            "amplified_charge",
            measured_tag,
        )
        written.append(output_path / f"{measured_tag}_amplified_charge.pdf")
    if _has_distribution(amplified_amplitude):
        waveform_stats.WaveformStatistics.amplitude_fit(
            drawer,
            amplified_amplitude,
            "amplified_amplitude",
            measured_tag,
        )
        written.append(output_path / f"{measured_tag}_amplified_amplitude.pdf")
    if _has_distribution(e_dep):
        waveform_stats.WaveformStatistics.amplitude_fit(
            drawer,
            e_dep,
            "e_dep",
            truth_tag,
        )
        written.append(output_path / f"{truth_tag}_e_dep.pdf")
    if _has_distribution(generated_charge):
        waveform_stats.WaveformStatistics.amplitude_fit(
            drawer,
            generated_charge,
            "generated_charge_fC",
            truth_tag,
        )
        written.append(output_path / f"{truth_tag}_generated_charge_fC.pdf")
    return written


def collect(kwargs):
    run_root = _run_root(kwargs)
    batch_path = run_root / "batch"
    output_path = run_root / "analysis"
    create_path(output_path)

    columns = _read_event_arrays(batch_path)
    summary = _summary(columns)
    with open(output_path / "cce_summary_stats.json", "w") as f_out:
        json.dump(summary, f_out, indent=2, sort_keys=True)
        f_out.write("\n")

    preview_paths = _plot_with_existing_functions(columns, output_path)
    print(f"CCE summary entries: {summary['events']}")
    print(f"CCE summary stats: {output_path / 'cce_summary_stats.json'}")
    for preview_path in preview_paths:
        print(f"CCE summary preview: {preview_path}")
