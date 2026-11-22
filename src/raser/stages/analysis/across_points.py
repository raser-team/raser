"""The results of the points of an experiment side by side."""

import json
from pathlib import Path

from raser.supports import figures


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
