"""Times of the events of one point of an experiment."""

import numpy as np

from raser.core.analysis.resolution import core_width
from raser.core.readout.waveforms import read_waveforms
from raser.core.reconstruction.event import net_pulse
from raser.core.reconstruction.event import pulse_polarity
from raser.stages.reconstruction import job_table

from .files import job_file
from .files import slice_file


CFD_FRACTIONS = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)


def point_tables(jobs, threshold, amplitude_threshold):
    """The reconstruction of each finished job of a point that recorded
    events, as (place of the job in `jobs`, its table). Until the chain has
    the reconstruction slice the tables are made here, from the files of
    the jobs, with the fractions CFD_FRACTIONS and one sign of the pulses
    for the point, taken from all its events.

    jobs : (seed folder, job index) pairs, as lifecycle hands them out.
    threshold, amplitude_threshold : in the unit of the waveforms [V]
    """
    readouts = []
    for place, (folder, index) in enumerate(jobs):
        path = job_file(folder, index, "readout")
        if path is not None:
            readouts.append((place, folder, index, read_waveforms(path)))
    if not readouts:
        return []
    polarity = pulse_polarity(
        [net_pulse(samples)[0] for *_, waveforms in readouts for event in waveforms.events for samples in event.voltage]
    )
    tables = []
    for place, folder, index, waveforms in readouts:
        files = [slice_file(folder, index, name) for name in ("deposit", "current")]
        tables.append((place, job_table(waveforms, *files, threshold, amplitude_threshold, CFD_FRACTIONS, polarity)))
    return tables


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
    for _, table in tables:
        if len(table.electrodes) > 1:
            raise NotImplementedError(
                f"{len(table.electrodes)} electrodes; "
                "the time of an event with several electrodes is not settled"
            )
    names = ["job", "event", "ToA", "ToT", "amplitude", "baseline", "noise", "truth", "CoG"]
    columns = {name: [] for name in names}
    for place, table in tables:
        rows = table.columns
        chosen = rows["selected"]
        columns["job"].append(np.full(int(np.sum(chosen)), float(place)))
        columns["event"].append(rows["event"][chosen].astype("float64"))
        for name in ("ToA", "ToT", "amplitude", "baseline", "noise", "CoG"):
            columns[name].append(rows[name][chosen, 0])
        columns["truth"].append(rows["deposit_time"][chosen])
        for k, part in enumerate(table.fractions):
            columns.setdefault(f"CFD{round(100 * part)}", []).append(rows["CFD"][chosen, 0, k])
    count = sum(len(table) for _, table in tables)
    return count, tables[0][1].polarity, {name: np.concatenate(values) for name, values in columns.items()}


def time_widths(times):
    """For ToA, CoG, CFD10 ... CFD90 of `event_times` what `core_width` gives
    for time - truth [s], and `missing`: the events that have no such time."""
    widths = {}
    for name in ["ToA", "CoG"] + [f"CFD{round(100 * part)}" for part in CFD_FRACTIONS]:
        difference = times[name] - times["truth"]
        found = ~np.isnan(difference)
        widths[name] = {**core_width(difference[found]), "missing": int(np.sum(~found))}
    return widths


def point_resolution(jobs, threshold, amplitude_threshold):
    """Time resolution of one point: for every time of `event_times`, the
    width of the core of time - truth over the events above the amplitude
    threshold.

    Returns a dict:
        events    number of events
        selected  number of them above the amplitude threshold
        polarity  sign of the pulses, +1 or -1
        times     what `time_widths` gives for the selected events
    """
    count, polarity, times = event_times(point_tables(jobs, threshold, amplitude_threshold))
    return {
        "events": count,
        "selected": len(times["truth"]),
        "polarity": polarity,
        "times": time_widths(times),
    }
