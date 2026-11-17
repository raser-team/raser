"""Charge collection efficiency of one point of an experiment."""

import numpy as np

from raser.core.current.currents import read_currents
from raser.core.metrics.collection import collection_efficiency

from .files import job_file


def event_efficiencies(jobs):
    """Efficiency of every event of the finished jobs of a point.

    jobs : (seed folder, job index) pairs, as lifecycle hands them out.

    A job that recorded no event has a deposits file without events and no
    currents file; it adds nothing.
    """
    efficiencies = []
    for folder, index in jobs:
        path = job_file(folder, index, "currents")
        if path is None:
            continue
        events = read_currents(path).events
        efficiencies.append(
            collection_efficiency(
                [event.charge for event in events], [event.pairs for event in events]
            )
        )
    return np.concatenate(efficiencies) if efficiencies else np.empty(0)


def efficiency_spread(efficiencies):
    """Number of efficiencies, their mean, its standard error and their
    standard deviation."""
    count = len(efficiencies)
    if count < 2:
        raise ValueError(f"{count} events in the point, a mean and a spread need at least 2")
    spread = float(np.std(efficiencies, ddof=1))
    return {
        "events": count,
        "mean": float(np.mean(efficiencies)),
        "mean_error": spread / np.sqrt(count),
        "spread": spread,
    }


def point_efficiency(jobs):
    """`efficiency_spread` of the events of a point."""
    return efficiency_spread(event_efficiencies(jobs))
