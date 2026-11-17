"""The results of one point of an experiment, as one digitizer sees it."""

import json
from pathlib import Path

import h5py

from . import plots
from .collection import efficiency_spread
from .collection import event_efficiencies
from .timing import event_times
from .timing import point_tables
from .timing import time_widths

MILLIVOLT = 1.0e-3  # V


def write_point(jobs, digitizer, edge, folder):
    """Write the results of a point into `folder`: result.json, events.h5 and
    the plots.

    jobs : (seed folder, job index) pairs, as lifecycle hands them out.
    digitizer : content of a file of components/adc: `threshold` and
        `amplitude_threshold` [mV]
    edge : "rising" or "falling", the edge of the pulses they are set on

    result.json:
        digitizer   as given
        collection  what `efficiency_spread` gives for the events of the
                    point; the efficiency is of the currents and does not
                    see the digitizer. With fewer than 2 events, `events`
                    and `error` in place of the rest
        timing      events, selected, polarity and times, as
                    `point_resolution` gives them [s]; or `error` in place of
                    `times` when the selected events give no width, and of
                    `polarity` too when the point has no event

    events.h5: one dataset per quantity of `event_times`, one value per
    selected event; the times are in s, the voltages in V.

    Returns what the point has no result of and why, or None.
    """
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    tables = point_tables(
        jobs, digitizer["threshold"] * MILLIVOLT, digitizer["amplitude_threshold"] * MILLIVOLT, edge
    )
    efficiencies = event_efficiencies(tables)
    result = {"digitizer": digitizer}
    missing = []
    try:
        result["collection"] = efficiency_spread(efficiencies)
    except ValueError as too_few:
        result["collection"] = {"events": len(efficiencies), "error": str(too_few)}
        missing.append(f"no efficiency: {too_few}")
    else:
        plots.draw_efficiencies(efficiencies, folder / "efficiency.png")
    if not len(efficiencies):
        result["timing"] = {"events": 0, "selected": 0, "error": "the jobs recorded no event"}
        missing.append("no time resolution: the jobs recorded no event")
        (folder / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        return "; ".join(missing)

    count, polarity, times = event_times(tables)
    with h5py.File(folder / "events.h5", "w") as file:
        for name, values in times.items():
            file[name] = values.astype("int64") if name in ("job", "event") else values
    result["timing"] = {"events": count, "selected": len(times["truth"]), "polarity": polarity}
    plots.draw_amplitudes(times["amplitude"], digitizer["amplitude_threshold"] * MILLIVOLT, count, folder / "amplitude.png")
    try:
        widths = time_widths(times)
    except ValueError as too_few:
        result["timing"]["error"] = str(too_few)
        missing.append(f"no time resolution: {too_few}")
    else:
        result["timing"]["times"] = widths
        plots.draw_differences(times, widths, folder / "time_difference.png")
        plots.draw_fractions(widths, folder / "resolution_of_fraction.png")
    (folder / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    return "; ".join(missing) or None
