"""Times of the events of one point of an experiment."""

import numpy as np

from raser.core.readout.waveforms import read_waveforms
from raser.core.interaction.deposits import read_deposits
from raser.core.metrics.reconstruction import InputWaveform
from raser.core.metrics.reconstruction import get_CFD50
from raser.core.metrics.reconstruction import get_CoG
from raser.core.metrics.reconstruction import net_pulse
from raser.core.metrics.reconstruction import pulse_polarity
from raser.core.metrics.resolution import core_width

from .files import job_file
from .files import slice_file


CFD_FRACTIONS = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)


def event_times(jobs, threshold, amplitude_threshold):
    """Times and amplitude of the events of the finished jobs of a point.

    jobs : (seed folder, job index) pairs, as lifecycle hands them out.
    threshold, amplitude_threshold : in the unit of the waveforms [V]

    Every waveform is taken without its baseline and with its pulse turned
    positive; the thresholds and the amplitude are above the baseline. The
    sign of the pulses is one for the point, taken from all its events.

    Returns the number of events, the sign of the pulses (+1 or -1) and, for
    the events above the amplitude threshold, one array per quantity:
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
    names = ["job", "event", "ToA", "ToT", "amplitude", "baseline", "noise", "truth", "CoG"] + [f"CFD{round(100 * part)}" for part in CFD_FRACTIONS]
    events = []
    for place, (folder, index) in enumerate(jobs):
        path = job_file(folder, index, "waveforms")
        if path is None:
            continue
        waveforms = read_waveforms(path)
        if len(waveforms.electrodes) > 1:
            raise NotImplementedError(
                f"{path}: {len(waveforms.electrodes)} electrodes; "
                "the time of an event with several electrodes is not settled"
            )
        deposits = read_deposits(str(slice_file(folder, index, "deposits")))
        earliest = {event.event: min(event.t) for event in deposits.events}
        for event in waveforms.events:
            if event.event not in earliest:
                raise ValueError(f"{path}: event {event.event} is not among the deposits of the job")
            events.append(
                (place, event.event, event.t0, waveforms.dt, earliest[event.event], *net_pulse(event.voltage[0]))
            )
    if not events:
        raise ValueError("the jobs recorded no event")
    polarity = pulse_polarity([net for _, _, _, _, _, net, _, _ in events])
    rows = []
    for place, number, t0, dt, truth, net, baseline, noise in events:
        one = InputWaveform(
            [polarity * net], t0, dt, None, threshold, amplitude_threshold, None, None
        )
        if one.data["amplitude"] is None:
            continue
        fractions = [
            get_CFD50(one.times, one.waveforms[0], part, one.peak_time[0])
            for part in CFD_FRACTIONS
        ]
        center = get_CoG(one.times, one.waveforms[0], threshold, one.peak_time[0])
        rows.append(
            [place, number, one.data["ToA"], one.data["ToT"], one.data["amplitude"], baseline, noise, truth, center, *fractions]
        )
    table = np.array(rows, dtype="float64").reshape(len(rows), len(names))
    return len(events), polarity, {name: table[:, k] for k, name in enumerate(names)}


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
    count, polarity, times = event_times(jobs, threshold, amplitude_threshold)
    return {
        "events": count,
        "selected": len(times["truth"]),
        "polarity": polarity,
        "times": time_widths(times),
    }
