"""Charge collection efficiency of one point of an experiment."""

import numpy as np

from raser.core.current.currents import read_currents
from raser.core.analysis.collection import collection_efficiency

from .files import job_file


def event_efficiencies(tables):
    """Efficiency of every event of a point, from the currents of its jobs.

    tables : what `point_tables` gives; the currents of a job must hold the
        events of its reconstruction table, no more and no fewer.
    """
    efficiencies = []
    for _, folder, index, table in tables:
        path = job_file(folder, index, "current")
        events = read_currents(path).events
        numbers, rows = sorted(event.event for event in events), sorted(int(number) for number in table.columns["event"])
        if numbers != rows:
            raise ValueError(
                f"{path}: events {sorted(set(numbers) ^ set(rows))} are in the currents "
                "or in the reconstruction of the job, not in both"
            )
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
