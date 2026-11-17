"""Times of the events of one point of an experiment."""

import numpy as np

from raser.core.analysis.resolution import core_width
from raser.core.deposit.deposits import read_deposits
from raser.core.reconstruction.event_table import EDGE_SIGN
from raser.core.reconstruction.event_table import read_event_table

from .files import job_file
from .files import slice_file


def point_tables(jobs):
    """The reconstruction tables of the finished jobs of a point that
    recorded events, as (place of the job in `jobs`, seed folder, job index,
    table). The tables of a point were made with the same thresholds,
    fractions and edge.

    jobs : (seed folder, job index) pairs, as lifecycle hands them out.
    """
    tables = []
    for place, (folder, index) in enumerate(jobs):
        path = job_file(folder, index, "reconstruction")
        if path is not None:
            tables.append((place, folder, index, read_event_table(path)))
    settings = {table_setting(table) for *_, table in tables}
    if len(settings) > 1:
        raise ValueError(f"the jobs of the point were reconstructed with different settings: {sorted(settings)}")
    return tables


def table_setting(table):
    """Thresholds [mV], fractions and edge of a table, as one hashable value."""
    return (round(table.threshold / 1.0e-3, 9), round(table.amplitude_threshold / 1.0e-3, 9), table.fractions, table.edge)


def event_times(tables):
    """Times and amplitude of the selected events of a point.

    tables : what `point_tables` gives

    Every waveform was taken without its baseline and with its pulse turned
    positive; the thresholds and the amplitude are above the baseline.

    Returns the number of events, the sign of the pulses (+1 or -1) and, for
    the selected events, one array per quantity:
        job         place of the job of the event in `jobs`
        event       Geant4 number of the event in its job
        ToA         time of arrival [s]
        ToT         time over threshold [s]
        amplitude   [V]
        baseline    mean of the samples before the pulse [V]
        noise       their standard deviation [V]
        truth       time of the earliest deposit of the event [s]
        CoG         centre of gravity in time of the part above the threshold [s]
        CFD10 ... CFD90   constant-fraction time at 10 % ... 90 % of the amplitude [s]
    """
    if not tables:
        raise ValueError("the jobs recorded no event")
    for *_, table in tables:
        if len(table.electrodes) > 1:
            raise NotImplementedError(
                f"{len(table.electrodes)} electrodes; "
                "the time of an event with several electrodes is not settled"
            )
    names = ["job", "event", "ToA", "ToT", "amplitude", "baseline", "noise", "truth", "CoG"]
    columns = {name: [] for name in names}
    for place, folder, index, table in tables:
        deposits = slice_file(folder, index, "deposit")
        earliest = {event.event: min(event.t) for event in read_deposits(str(deposits)).events}
        rows = table.columns
        chosen = rows["selected"]
        for number in rows["event"]:
            if number not in earliest:
                raise ValueError(f"{deposits}: event {number} is not among the deposits of the job")
        columns["job"].append(np.full(int(np.sum(chosen)), float(place)))
        columns["event"].append(rows["event"][chosen].astype("float64"))
        for name in ("ToA", "ToT", "amplitude", "baseline", "noise", "CoG"):
            columns[name].append(rows[name][chosen, 0])
        columns["truth"].append(np.array([earliest[number] for number in rows["event"][chosen]], dtype="float64"))
        for k, part in enumerate(table.fractions):
            columns.setdefault(f"CFD{round(100 * part)}", []).append(rows["CFD"][chosen, 0, k])
    count = sum(len(table) for *_, table in tables)
    return count, EDGE_SIGN[tables[0][3].edge], {name: np.concatenate(values) for name, values in columns.items()}


def time_widths(times):
    """For ToA, CoG, CFD10 ... CFD90 of `event_times` what `core_width` gives
    for time - truth [s], and `missing`: the events that have no such time."""
    widths = {}
    for name in ["ToA", "CoG"] + [name for name in times if name.startswith("CFD")]:
        difference = times[name] - times["truth"]
        found = ~np.isnan(difference)
        widths[name] = {**core_width(difference[found]), "missing": int(np.sum(~found))}
    return widths


def point_resolution(jobs):
    """Time resolution of one point: for every time of `event_times`, the
    width of the core of time - truth over the events above the amplitude
    threshold.

    Returns a dict:
        events    number of events
        selected  number of them above the amplitude threshold
        polarity  sign of the pulses, +1 or -1
        times     what `time_widths` gives for the selected events
    """
    count, polarity, times = event_times(point_tables(jobs))
    return {
        "events": count,
        "selected": len(times["truth"]),
        "polarity": polarity,
        "times": time_widths(times),
    }
