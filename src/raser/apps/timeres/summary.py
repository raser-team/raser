"""Time-resolution run summary."""

import json
from pathlib import Path

from raser.core.device import build_device as bdv
from raser.core.metrics import waveform_stats
from raser.supports.output import create_path


def _load_run_record(run_root):
    with open(Path(run_root) / "run.json") as f_in:
        return json.load(f_in)


def _component(record, kind):
    matches = [item for item in record["components"] if item["kind"] == kind]
    if len(matches) != 1:
        raise ValueError(f"Timeres run record requires one {kind} component")
    return matches[0]


def _configure_detector(record):
    device = record["device"]
    detector = bdv.Detector(device["definition"])
    detector.voltage = float(device["state"]["bias_voltage"])
    detector.amplifier = _component(record, "AFE")["name"]
    detector.daq = _component(record, "ADC")["name"]
    return detector


def _thresholds(record):
    daq = _component(record, "ADC")["values"]
    return daq["threshold"], daq["amplitude_threshold"]


def collect(run_root):
    run_root = Path(run_root)
    record = _load_run_record(run_root)
    detector = _configure_detector(record)
    threshold, amplitude_threshold = _thresholds(record)
    output_path = run_root / "analysis"
    create_path(output_path)

    statistics = waveform_stats.WaveformStatistics.from_batch(
        run_root / "batch",
        detector,
        threshold,
        amplitude_threshold,
    )
    if not statistics.data:
        raise ValueError(
            f"Timeres run contains no accepted waveform events: {run_root}"
        )
    statistics.draw(output_path, record["run"])
