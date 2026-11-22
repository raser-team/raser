"""Figures of filtered analogue traces, sample points, and ADC codes."""

import numpy as np

from raser.supports import figures


def draw_samples(
    folder, event_number, times_s, filtered_V, sample_times_s, sample_V, names
):
    """Draw ``samples_<event_number>``: analogue traces (lines) and sample points (dots).

    ``times_s`` is the bin-centre time (s) of the filtered traces, shape
    ``(bins,)``; ``filtered_V`` is ``(electrodes, bins)`` in V; ``sample_times_s``
    and ``sample_V`` are ``(electrodes, samples)`` in s and V; ``names`` has one
    electrode name per row.
    """
    colours = figures.series(len(names), ordered=False)
    figure, axis = figures.new()
    for row, name in enumerate(names):
        axis.plot(
            np.asarray(times_s) / figures.UNIT["ns"],
            np.asarray(filtered_V[row]) / figures.UNIT["mV"],
            color=colours[row],
            label=name,
        )
        axis.plot(
            np.asarray(sample_times_s[row]) / figures.UNIT["ns"],
            np.asarray(sample_V[row]) / figures.UNIT["mV"],
            ".",
            color=colours[row],
        )
    axis.set_xlabel(figures.label("Time", "ns"))
    axis.set_ylabel(figures.label("Amplitude", "mV"))
    axis.legend()
    return figures.save(figure, folder, "samples", event_number)


def draw_codes(folder, codes, bits):
    """Draw ``codes``: histogram of all stored ADC codes, one bin per code in ``[0, 2**bits)``."""
    maximum = 1 << int(bits)
    figure, axis = figures.new()
    axis.hist(
        np.asarray(codes).ravel(),
        bins=np.arange(maximum + 1) - 0.5,
        color=figures.HISTOGRAM,
    )
    axis.set_xlabel("Code")
    axis.set_ylabel("Events")
    return figures.save(figure, folder, "codes")
