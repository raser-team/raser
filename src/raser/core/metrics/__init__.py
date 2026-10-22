"""Waveform and readout metrics."""

from .waveform import WaveformMeasurements
from .waveform import measure_waveform

__all__ = ["WaveformMeasurements", "measure_waveform"]


def main(kwargs):
    from . import waveform_stats

    waveform_stats.main(kwargs)
