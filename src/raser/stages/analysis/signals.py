"""The deposited energy and the induced current of the events of a point."""

import numpy as np

from raser.core.current.currents import read_currents
from raser.core.deposit.deposits import read_deposits

from .files import job_file
from .files import slice_file


def event_energies(jobs):
    """Deposited energy of every recorded event of a point [MeV]: the sum of
    the energies of its deposits. The deposits file holds only what lies in
    the sensitive layers, of all detectors together.

    jobs : (experiment folder, slice -> node) pairs, as lifecycle hands them out
    """
    energies = [
        sum(event.e)
        for experiment, nodes in jobs
        for event in read_deposits(str(slice_file(experiment, nodes, "deposit"))).events
    ]
    return np.array(energies, dtype="float64")


def energy_spread(energies):
    """Number of energies, their mean and their standard deviation [MeV], or
    `events` and `error` in place of the last two for fewer than 2 events."""
    count = len(energies)
    if count < 2:
        return {"events": count, "error": f"{count} events in the point, a mean and a spread need at least 2"}
    return {"events": count, "mean": float(np.mean(energies)), "std": float(np.std(energies, ddof=1))}


def mean_current(jobs):
    """The induced current of the recorded events of a point, averaged over
    the events, as (bin centres [s], current [A], number of events), or None
    when the jobs recorded no event.

    The current of an event is the sum over its electrodes, on the time axis
    of the primary. The bins of an event start at its own `t0`: each is shared
    between the two bins of the common axis that it overlaps, in proportion to
    the overlap, so that the charge of the event is kept. Where an event has
    no bin its current is zero, and every recorded event counts in the mean.

    jobs : (experiment folder, slice -> node) pairs, as lifecycle hands them out
    """
    records, step = [], None
    for experiment, nodes in jobs:
        path = job_file(experiment, nodes, "current")
        if path is None:
            continue
        currents = read_currents(path)
        if step is not None and currents.dt != step:
            raise ValueError(f"{path}: time bins of {currents.dt} s, those of the other jobs are {step} s wide")
        step = currents.dt
        records += [(event.t0, event.current.sum(axis=0)) for event in currents.events]
    if not records:
        return None
    start = min(t0 for t0, _ in records)
    # offsets that are whole bins up to rounding stay whole bins
    places = [round((t0 - start) / step, 9) for t0, _ in records]
    total = np.zeros(max(int(np.ceil(place)) + len(current) for place, (_, current) in zip(places, records)))
    for place, (_, current) in zip(places, records):
        first = int(np.floor(place))
        later = place - first
        total[first : first + len(current)] += (1.0 - later) * current
        if later:
            total[first + 1 : first + 1 + len(current)] += later * current
    return start + (np.arange(len(total)) + 0.5) * step, total / len(records), len(records)
