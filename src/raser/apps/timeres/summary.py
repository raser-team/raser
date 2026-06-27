"""Time-resolution run summary."""

import json
from pathlib import Path

from raser.core.device import build_device as bdv
from raser.core.metrics import waveform_stats
from raser.supports.output import create_path
from raser.supports.paths import component_path


def _load_run_record(run_root):
    with open(Path(run_root) / "run.json") as f_in:
        return json.load(f_in)


def _configure_detector(record):
    detector = bdv.Detector(record["sensor"])
    detector.voltage = float(record["voltage"])
    if record.get("amplifier") is not None:
        detector.amplifier = record["amplifier"]
    if record.get("daq") is not None:
        detector.daq = record["daq"]
    return detector


def _thresholds(detector):
    with open(component_path("electronics", "digital", detector.daq + ".json")) as f_in:
        daq = json.load(f_in)
    return daq["threshold"], daq["amplitude_threshold"]


def collect(run_root):
    run_root = Path(run_root)
    record = _load_run_record(run_root)
    detector = _configure_detector(record)
    threshold, amplitude_threshold = _thresholds(detector)
    output_path = run_root / "analysis"
    create_path(output_path)

    statistics = waveform_stats.WaveformStatistics.from_batch(
        run_root / "batch",
        detector,
        threshold,
        amplitude_threshold,
    )
    statistics.draw(output_path, record["run"])
