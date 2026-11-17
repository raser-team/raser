"""Plots of the results of one point."""

import math

import matplotlib.pyplot as plt
import numpy as np

from .timing import CFD_FRACTIONS

PICOSECOND = 1.0e-12  # s
MILLIVOLT = 1.0e-3  # V


def draw_efficiencies(efficiencies, path):
    """Distribution of the charge collection efficiency of the events."""
    figure, axis = plt.subplots(figsize=(6, 4))
    axis.hist(efficiencies, bins=60, histtype="stepfilled", alpha=0.6)
    axis.axvline(np.mean(efficiencies), color="k", linestyle="--")
    axis.set_xlabel("charge collection efficiency")
    axis.set_ylabel("events")
    axis.set_title(f"{len(efficiencies)} events, mean {np.mean(efficiencies):.4f}")
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)


def draw_amplitudes(amplitudes, amplitude_threshold, events, path):
    """Distribution of the amplitude of the events above the amplitude
    threshold [V], out of `events` events."""
    figure, axis = plt.subplots(figsize=(6, 4))
    axis.hist(np.asarray(amplitudes) / MILLIVOLT, bins=60, histtype="stepfilled", alpha=0.6)
    axis.axvline(amplitude_threshold / MILLIVOLT, color="k", linestyle="--")
    axis.set_xlabel("amplitude above the baseline [mV]")
    axis.set_ylabel("events")
    axis.set_title(f"{len(amplitudes)} of {events} events above {amplitude_threshold / MILLIVOLT:g} mV")
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)


def draw_differences(times, widths, path):
    """One panel per time of `event_times`: the distribution of time - truth
    around its core, the last window of the fit and the fitted Gaussian."""
    names = list(widths)
    figure, axes = plt.subplots(3, 4, figsize=(16, 10))
    for axis, name in zip(axes.flat, names):
        width = widths[name]
        difference = times[name] - times["truth"]
        difference = difference[~np.isnan(difference)] / PICOSECOND
        mean, sigma = width["mean"] / PICOSECOND, width["sigma"] / PICOSECOND
        low, high = (edge / PICOSECOND for edge in width["window"])
        edges = np.linspace(mean - 8 * sigma, mean + 8 * sigma, 65)
        axis.hist(difference, bins=edges, histtype="stepfilled", alpha=0.5)
        axis.axvspan(low, high, color="0.85", zorder=0)
        # the Gaussian that has the events of the window inside the window
        inside = 0.5 * (
            math.erf((high - mean) / (sigma * math.sqrt(2)))
            - math.erf((low - mean) / (sigma * math.sqrt(2)))
        )
        x = np.linspace(low, high, 200)
        density = np.exp(-0.5 * ((x - mean) / sigma) ** 2) / (sigma * math.sqrt(2 * math.pi))
        axis.plot(x, width["window_events"] * (edges[1] - edges[0]) * density / inside, "r")
        axis.set_title(
            f"{name}: sigma68 {width['sigma68'] / PICOSECOND:.1f} ps, "
            f"sigma {sigma:.1f} +- {width['sigma_error'] / PICOSECOND:.1f} ps\n"
            f"{width['window_events']} of {width['events']} events in the window",
            fontsize=9,
        )
        axis.set_xlabel(f"{name} - truth [ps]")
    for axis in axes.flat[len(names):]:
        axis.set_visible(False)
    figure.tight_layout()
    figure.savefig(path, dpi=130)
    plt.close(figure)


def draw_fractions(widths, path):
    """Width of the core of CFD - truth against the fraction of the CFD."""
    fractions = np.array(CFD_FRACTIONS)
    chosen = [widths[f"CFD{round(100 * part)}"] for part in CFD_FRACTIONS]
    figure, axis = plt.subplots(figsize=(6, 4))
    axis.errorbar(
        fractions,
        [width["sigma"] / PICOSECOND for width in chosen],
        [width["sigma_error"] / PICOSECOND for width in chosen],
        fmt="o", capsize=3, label="sigma of the Gaussian",
    )
    axis.plot(fractions, [width["sigma68"] / PICOSECOND for width in chosen], "s", mfc="none", label="sigma68")
    axis.set_xlabel("fraction of the CFD")
    axis.set_ylabel("width of time - truth [ps]")
    axis.set_ylim(bottom=0)
    axis.grid(alpha=0.3)
    axis.legend()
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)
