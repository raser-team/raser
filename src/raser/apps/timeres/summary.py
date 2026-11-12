"""Time-resolution run summary."""

import json
from pathlib import Path

from raser.apps.signal.runtime import component_name
from raser.core.device import build_device as bdv
from raser.core.metrics import waveform_stats
from raser.supports.output import create_path


def collect_point(point_root, jobs):
    """Time-resolution plots of one point from the seed folders with finished jobs."""
    record = json.loads((Path(jobs[0][0]) / "run.json").read_text("utf-8"))
    options = {**record["options"], "_files": record["files"]}
    detector = bdv.Detector(record["files"]["device"]["det_name"])
    detector.voltage = float(options["voltage"])
    detector.amplifier = component_name(options, "afe", "amplifier")
    detector.daq = component_name(options, "adc", "adc")
    threshold = record["files"]["adc"]["threshold"]
    amplitude_threshold = record["files"]["adc"]["amplitude_threshold"]
    output_path = Path(point_root) / "analysis"
    create_path(output_path)

    statistics = waveform_stats.WaveformStatistics(
        detector, threshold, amplitude_threshold
    )
    for folder in dict.fromkeys(folder for folder, _ in jobs):
        statistics.read_batch(Path(folder) / "batch")
    if not statistics.data:
        raise ValueError(
            f"Timeres point contains no accepted waveform events: {point_root}"
        )
    statistics.draw(output_path, Path(point_root).name)
    return {}
