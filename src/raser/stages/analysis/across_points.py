"""The results of the points of an experiment side by side."""

import json
from pathlib import Path

import numpy as np

from raser.supports import figures

from .signals import event_energies
from .signals import mean_current

KEV_PER_MEV = 1.0e3


def scanned_options(points):
    """The options that do not have the same value in all points.

    points : (folder name, options) of each point
    """
    keys = sorted({key for _, options in points for key in options})
    return [key for key in keys if len({json.dumps(options.get(key)) for _, options in points}) > 1]


def write_points(points, results, folder):
    """Write points.json into `folder`: one row per point with its scanned
    options and, from its result.json, the number of events, the efficiency
    and its error, the number of selected events and for every time its
    sigma68, sigma and sigma_error [s]; and `energy_resolution`: of the charge
    and of the amplitude that have one, the FWHM / mean of all values
    (`resolution`) and of their core (`core_resolution`). A point without a time resolution has
    no times in its row, one without an efficiency None for it and its error.

    With one scanned option that is a number, also trend.png and trend.pdf: the
    efficiency and the sigma of each CFD fraction against it.

    points  : (folder name, options) of each point
    results : the content of result.json of each point
    """
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    scanned = scanned_options(points)
    rows = []
    for (name, options), result in zip(points, results):
        row = {
            "point": name,
            **{key: options.get(key) for key in scanned},
            "events": result["collection"]["events"],
            "efficiency": result["collection"].get("mean"),
            "efficiency_error": result["collection"].get("mean_error"),
            "selected": result["timing"]["selected"],
        }
        row["energy_resolution"] = {
            name: {key: entry[key] for key in ("resolution", "core_resolution")}
            for name, entry in result["energy_resolution"].items()
            if "error" not in entry
        }
        for time, width in result["timing"].get("times", {}).items():
            row[time] = {key: width[key] for key in ("sigma68", "sigma", "sigma_error")}
        rows.append(row)
    (folder / "points.json").write_text(json.dumps(rows, indent=2) + "\n")

    numbers = len(scanned) == 1 and all(
        isinstance(row[scanned[0]], (int, float)) and not isinstance(row[scanned[0]], bool) for row in rows
    )
    if not numbers:
        return
    key = scanned[0]
    rows = sorted(rows, key=lambda row: row[key])
    figure, (left, right) = figures.new(1, 2)
    collected = [row for row in rows if row["efficiency"] is not None]
    left.errorbar(
        [row[key] for row in collected],
        [row["efficiency"] for row in collected],
        [row["efficiency_error"] for row in collected],
        fmt="o-", color="black", capsize=3,
    )
    left.set_xlabel(key)
    left.set_ylabel(figures.label("Charge collection efficiency"))
    timed = [row for row in rows if "ToA" in row]
    names = [name for name in timed[0] if name.startswith("CFD")] if timed else []
    for name, color in zip(names, figures.series(len(names), True)):
        right.errorbar(
            [row[key] for row in timed],
            [row[name]["sigma"] / figures.UNIT["ps"] for row in timed],
            [row[name]["sigma_error"] / figures.UNIT["ps"] for row in timed],
            fmt="o-", color=color, capsize=2, label=name,
        )
    right.set_xlabel(key)
    right.set_ylabel(figures.label("Time resolution", "ps"))
    right.set_ylim(bottom=0)
    right.legend(ncol=3)
    figures.save(figure, folder, "trend")

    figure, axes = figures.new(1, 2)
    for axis, name in zip(axes, ("charge", "amplitude")):
        measured = [row for row in rows if name in row["energy_resolution"]]
        for field, marker, text in (("resolution", "o-", "FWHM / mean"), ("core_resolution", "s--", "FWHM / mean of the core")):
            axis.plot(
                [row[key] for row in measured],
                [row["energy_resolution"][name][field] for row in measured],
                marker, color="black" if field == "resolution" else figures.HISTOGRAM, label=text,
            )
        axis.set_xlabel(key)
        axis.set_ylabel(figures.label(f"Energy resolution of the {name}"))
        axis.set_ylim(bottom=0)
        axis.legend()
    figures.save(figure, folder, "energy_resolution")


def write_signals(points, jobs, folder):
    """Write currents.png and deposited_energy.png (and .pdf) into `folder`,
    one curve per point: the induced current averaged over the recorded events
    of the point against time, and the distribution of the energy the events
    deposited in the sensitive layers, in the same 60 bins for all points.

    A point whose jobs recorded no event has no curve; a figure that would
    have no curve is not drawn. The curves are labelled with the scanned
    options of the point, in ascending order of the option when there is one
    and it is a number.

    points : (folder name, options) of each point
    jobs   : the (seed folder, job index) pairs of each point
    """
    folder = Path(folder)
    scanned = scanned_options(points)
    entries = [
        (", ".join(f"{key} = {options.get(key)}" for key in scanned) or name, options, point_jobs)
        for (name, options), point_jobs in zip(points, jobs)
    ]
    numbers = len(scanned) == 1 and all(
        isinstance(options[scanned[0]], (int, float)) and not isinstance(options[scanned[0]], bool)
        for _, options, _ in entries
    )
    if numbers:
        entries.sort(key=lambda entry: entry[1][scanned[0]])
    colors = figures.series(len(entries), numbers)

    means = [(text, mean_current(point_jobs), color) for (text, _, point_jobs), color in zip(entries, colors)]
    means = [entry for entry in means if entry[1] is not None]
    if means:
        figure, axis = figures.new()
        for text, (times, current, _), color in means:
            axis.plot(times / figures.UNIT["ns"], current / figures.UNIT["uA"], color=color, label=text)
        axis.set_xlabel(figures.label("Time", "ns"))
        axis.set_ylabel(figures.label("Mean induced current", "uA"))
        axis.legend()
        figures.save(figure, folder, "currents")

    energies = [(text, event_energies(point_jobs) * KEV_PER_MEV, color) for (text, _, point_jobs), color in zip(entries, colors)]
    energies = [entry for entry in energies if len(entry[1])]
    if not energies:
        return
    edges = np.histogram_bin_edges(np.concatenate([values for _, values, _ in energies]), bins=60)
    figure, axis = figures.new()
    for text, values, color in energies:
        axis.hist(values, bins=edges, histtype="step", color=color, label=f"{text}: {len(values)} events")
    axis.set_xlabel(figures.label("Deposited energy", "keV"))
    axis.set_ylabel("Events")
    axis.legend()
    figures.save(figure, folder, "deposited_energy")
