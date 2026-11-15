"""Times of the events of one point of an experiment."""

import numpy as np

from raser.core.frontend.waveforms import read_waveforms
from raser.core.metrics.reconstruction import InputWaveform
from raser.core.metrics.reconstruction import get_CFD50
from raser.core.metrics.reconstruction import get_CoG

from .files import job_file


CFD_FRACTIONS = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)


def event_times(jobs, threshold, amplitude_threshold):
    """Times and amplitude of the events of the finished jobs of a point.

    jobs : (seed folder, job index) pairs, as lifecycle hands them out.
    threshold, amplitude_threshold : in the unit of the waveforms [V]

    Returns the number of events and, for those above the amplitude
    threshold, one array per quantity:
        ToA         time of arrival [s]
        ToT         time over threshold [s]
        amplitude   [V]
        CoG         centre of gravity in time of the part above the threshold [s]
        CFD10 ... CFD90   constant-fraction time at 10 % ... 90 % of the amplitude [s]
    """
    count = 0
    names = ["ToA", "ToT", "amplitude", "CoG"] + [f"CFD{round(100 * part)}" for part in CFD_FRACTIONS]
    rows = []
    for folder, index in jobs:
        path = job_file(folder, index, "waveforms")
        if path is None:
            continue
        waveforms = read_waveforms(path)
        if len(waveforms.electrodes) > 1:
            raise NotImplementedError(
                f"{path}: {len(waveforms.electrodes)} electrodes; "
                "the time of an event with several electrodes is not settled"
            )
        for event in waveforms.events:
            count += 1
            one = InputWaveform(
                event.voltage, event.t0, waveforms.dt, None, threshold, amplitude_threshold, None, None
            )
            if one.data["amplitude"] is None:
                continue
            fractions = [
                get_CFD50(one.times, one.waveforms[0], part, one.peak_time[0])
                for part in CFD_FRACTIONS
            ]
            center = get_CoG(one.times, one.waveforms[0], threshold, one.peak_time[0])
            rows.append(
                [one.data["ToA"], one.data["ToT"], one.data["amplitude"], center, *fractions]
            )
    table = np.array(rows, dtype="float64").reshape(len(rows), len(names))
    return count, {name: table[:, k] for k, name in enumerate(names)}
