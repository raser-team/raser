"""The results of the points of an experiment side by side."""

import json
from pathlib import Path

import matplotlib.pyplot as plt

from .timing import CFD_FRACTIONS

PICOSECOND = 1.0e-12  # s


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
    sigma68, sigma and sigma_error [s]. A point without a time resolution has
    no times in its row, one without an efficiency None for it and its error.

    With one scanned option that is a number, also points.png: the
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
    figure, (left, right) = plt.subplots(1, 2, figsize=(11, 4))
    collected = [row for row in rows if row["efficiency"] is not None]
    left.errorbar(
        [row[key] for row in collected],
        [row["efficiency"] for row in collected],
        [row["efficiency_error"] for row in collected],
        fmt="o-", capsize=3,
    )
    left.set_xlabel(key)
    left.set_ylabel("charge collection efficiency")
    left.grid(alpha=0.3)
    timed = [row for row in rows if "CFD50" in row]
    for part in CFD_FRACTIONS:
        name = f"CFD{round(100 * part)}"
        right.errorbar(
            [row[key] for row in timed],
            [row[name]["sigma"] / PICOSECOND for row in timed],
            [row[name]["sigma_error"] / PICOSECOND for row in timed],
            fmt="o-", capsize=2, label=name,
        )
    right.set_xlabel(key)
    right.set_ylabel("sigma of time - truth [ps]")
    right.set_ylim(bottom=0)
    right.grid(alpha=0.3)
    right.legend(ncol=3, fontsize=8)
    figure.tight_layout()
    figure.savefig(folder / "points.png", dpi=150)
    plt.close(figure)
