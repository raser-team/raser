"""Charge collection efficiency of one point of an experiment."""

import numpy as np

from raser.core.analysis.collection import collection_efficiency


def event_efficiencies(tables):
    """Efficiency of every event of a point, from the net charge and the
    pairs of its row.

    tables : (place of the job, table) of each job that recorded events
    """
    efficiencies = [
        collection_efficiency(table.columns["net_charge"], table.columns["pairs"]) for _, table in tables
    ]
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
