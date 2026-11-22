"""Plots of the results of one point."""

import math

import numpy as np

from raser.supports import figures


def draw_efficiencies(efficiencies, folder):
    """Distribution of the charge collection efficiency of the events."""
    figure, axis = figures.new()
    axis.hist(
        efficiencies, bins=60, histtype="stepfilled", color=figures.HISTOGRAM,
        label=f"{len(efficiencies)} events",
    )
    axis.axvline(
        np.mean(efficiencies), color="black", linestyle="--",
        label=f"mean {np.mean(efficiencies):.4f}",
    )
    axis.set_xlabel(figures.label("Charge collection efficiency"))
    figures.events(axis)
    axis.legend()
    figures.save(figure, folder, "efficiency")


def draw_amplitudes(amplitudes, amplitude_threshold, events, folder):
    """Distribution of the amplitude of the events above the amplitude
    threshold [V], out of `events` events."""
    figure, axis = figures.new()
    axis.hist(
        np.asarray(amplitudes) / figures.UNIT["mV"], bins=60, histtype="stepfilled",
        color=figures.HISTOGRAM, label=f"{len(amplitudes)} of {events} events",
    )
    axis.axvline(
        amplitude_threshold / figures.UNIT["mV"], color="black", linestyle="--",
        label=f"threshold {amplitude_threshold / figures.UNIT['mV']:g} mV",
    )
    axis.set_xlabel(figures.label("Amplitude", "mV"))
    figures.events(axis)
    axis.legend()
    figures.save(figure, folder, "amplitude")


def draw_differences(times, widths, folder):
    """One panel per time of `event_times`: the distribution of time - truth
    around its core, the last window of the fit and the fitted Gaussian."""
    names = list(widths)
    figure, axes = figures.new(3, 4)
    picosecond = figures.UNIT["ps"]
    for axis, name in zip(axes.flat, names):
        width = widths[name]
        difference = times[name] - times["truth"]
        difference = difference[~np.isnan(difference)] / picosecond
        mean, sigma = width["mean"] / picosecond, width["sigma"] / picosecond
        low, high = (edge / picosecond for edge in width["window"])
        edges = np.linspace(mean - 8 * sigma, mean + 8 * sigma, 65)
        counts, _, _ = axis.hist(difference, bins=edges, histtype="stepfilled", color=figures.HISTOGRAM)
        # room above the bars for the two lines of text
        axis.set_ylim(0, 1.35 * max(counts.max(), 1))
        axis.axvspan(low, high, color="0.85", zorder=0)
        # the Gaussian that has the events of the window inside the window
        inside = 0.5 * (
            math.erf((high - mean) / (sigma * math.sqrt(2)))
            - math.erf((low - mean) / (sigma * math.sqrt(2)))
        )
        x = np.linspace(low, high, 200)
        density = np.exp(-0.5 * ((x - mean) / sigma) ** 2) / (sigma * math.sqrt(2 * math.pi))
        axis.plot(
            x, width["window_events"] * (edges[1] - edges[0]) * density / inside,
            color="black",
        )
        axis.set_title(name)
        axis.text(
            0.03, 0.97,
            f"sigma68 {width['sigma68'] / picosecond:.1f} ps, "
            f"sigma {sigma:.1f} +- {width['sigma_error'] / picosecond:.1f} ps\n"
            f"{width['window_events']} of {width['events']} events in the window",
            fontsize=9, transform=axis.transAxes, va="top",
        )
        axis.set_xlabel(f"{name} - truth [ps]")
        figures.events(axis)
    for axis in axes.flat[len(names):]:
        axis.set_visible(False)
    figures.save(figure, folder, "time_difference")


def draw_fractions(widths, folder):
    """Width of the core of CFD - truth against the fraction of the CFD."""
    names = [name for name in widths if name.startswith("CFD")]
    fractions = np.array([int(name[3:]) / 100 for name in names])
    chosen = [widths[name] for name in names]
    picosecond = figures.UNIT["ps"]
    figure, axis = figures.new()
    axis.errorbar(
        fractions,
        [width["sigma"] / picosecond for width in chosen],
        [width["sigma_error"] / picosecond for width in chosen],
        fmt="o", color="black", capsize=3, label="sigma of the Gaussian",
    )
    axis.plot(
        fractions, [width["sigma68"] / picosecond for width in chosen],
        linestyle="none", marker="s", color="black", mfc="none", label="sigma68",
    )
    axis.set_xlabel("CFD fraction")
    axis.set_ylabel(figures.label("Time resolution", "ps"))
    axis.set_ylim(bottom=0)
    axis.legend()
    figures.save(figure, folder, "resolution_of_fraction")
