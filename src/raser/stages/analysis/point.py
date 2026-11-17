"""The results of one point of an experiment, as one digitizer sees it."""

import json
from pathlib import Path

import h5py

from . import plots
from .collection import efficiency_spread
from .collection import event_efficiencies
from .timing import event_times
from .timing import time_widths

MILLIVOLT = 1.0e-3  # V


def write_point(jobs, digitizer, folder):
    """Write the results of a point into `folder`: result.json, events.h5 and
    the plots.

    jobs : (seed folder, job index) pairs, as lifecycle hands them out.
    digitizer : content of a file of components/adc: `threshold` and
        `amplitude_threshold` [mV]

    result.json:
        digitizer   as given
        collection  what `efficiency_spread` gives for the events of the
                    point; the efficiency is of the currents and does not
                    see the digitizer
        timing      events, selected, polarity and times, as
                    `point_resolution` gives them [s]; or `error` in place of
                    `times` when the selected events give no width

    events.h5: one dataset per quantity of `event_times`, one value per
    selected event; the times are in s, the voltages in V.

    Returns the error of the timing, or None.
    """
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    efficiencies = event_efficiencies(jobs)
    result = {"digitizer": digitizer, "collection": efficiency_spread(efficiencies)}
    plots.draw_efficiencies(efficiencies, folder / "efficiency.png")

    count, polarity, times = event_times(
        jobs, digitizer["threshold"] * MILLIVOLT, digitizer["amplitude_threshold"] * MILLIVOLT
    )
    with h5py.File(folder / "events.h5", "w") as file:
        for name, values in times.items():
            file[name] = values.astype("int64") if name in ("job", "event") else values
    result["timing"] = {"events": count, "selected": len(times["truth"]), "polarity": polarity}
    plots.draw_amplitudes(times["amplitude"], digitizer["amplitude_threshold"] * MILLIVOLT, count, folder / "amplitude.png")
    error = None
    try:
        widths = time_widths(times)
    except ValueError as too_few:
        error = result["timing"]["error"] = str(too_few)
    else:
        result["timing"]["times"] = widths
        plots.draw_differences(times, widths, folder / "time_difference.png")
        plots.draw_fractions(widths, folder / "resolution_of_fraction.png")
    (folder / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    return error
