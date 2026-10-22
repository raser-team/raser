"""Sampled-current convolution."""

from __future__ import annotations

from typing import Callable

import numpy as np


def signal_convolution(
    signal_original, signal_convolved, responses: list[Callable[[float], float]]
) -> None:
    source_histogram = signal_original
    target_histogram = signal_convolved
    bin_count = source_histogram.GetNbinsX()
    if target_histogram.GetNbinsX() != bin_count:
        raise ValueError("Convolved signal must have the same number of bins")
    source_axis = source_histogram.GetXaxis()
    target_axis = target_histogram.GetXaxis()
    if (
        source_axis.GetXmin() != target_axis.GetXmin()
        or source_axis.GetXmax() != target_axis.GetXmax()
    ):
        raise ValueError("Convolved signal must have the same time range")

    time_step = source_histogram.GetBinWidth(1)
    if time_step <= 0:
        raise ValueError(f"Histogram bin width must be positive, got {time_step}")

    centers = np.array(
        [source_axis.GetBinCenter(index) for index in range(1, bin_count + 1)],
        dtype=np.float64,
    )
    source = np.array(
        [source_histogram.GetBinContent(index) for index in range(1, bin_count + 1)],
        dtype=np.float64,
    )
    for response in responses:
        convolved = np.zeros(bin_count, dtype=np.float64)
        for source_index, source_value in enumerate(source):
            if source_value == 0.0:
                continue
            kernel = np.array(
                [response(time - centers[source_index]) for time in centers],
                dtype=np.float64,
            )
            convolved += source_value * kernel * time_step
        source = convolved

    target_histogram.Reset()
    for index, value in enumerate(source, start=1):
        target_histogram.SetBinContent(index, float(value))
