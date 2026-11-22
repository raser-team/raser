"""Charge collection efficiency of one point of an experiment."""

import numpy as np

from raser.core.current.currents import read_currents
from raser.core.analysis.collection import collection_efficiency
from raser.core.analysis.resolution import NoSpread, TooFewValues, mad_core_resolution

from .files import job_file


def _job_events(tables):
    """The events of the currents of each job of `tables`, and the event
    numbers of its reconstruction table: those the trigger recorded, all of
    them among the currents."""
    for _, experiment, nodes, table in tables:
        path = job_file(experiment, nodes, "current")
        events = read_currents(path).events
        numbers, rows = {event.event for event in events}, {int(number) for number in table.columns["event"]}
        if rows - numbers:
            raise ValueError(f"{path}: events {sorted(rows - numbers)} are in the reconstruction of the job, not in its currents")
        yield events, rows


def event_efficiencies(tables):
    """Efficiency of every event of the currents of a point, recorded by the
    trigger or not.

    tables : what `point_tables` gives
    """
    efficiencies = [
        collection_efficiency([event.charge for event in events], [event.pairs for event in events])
        for events, _ in _job_events(tables)
    ]
    return np.concatenate(efficiencies) if efficiencies else np.empty(0)


def event_charges(tables):
    """Collected charge of every event of a point the trigger recorded [C]:
    the absolute value of the net charge of all read-out electrodes together,
    as in the efficiency.

    tables : what `point_tables` gives
    """
    charges = [
        np.abs([np.sum(event.charge) for event in events if event.event in rows])
        for events, rows in _job_events(tables)
    ]
    return np.concatenate(charges) if charges else np.empty(0)


def efficiency_spread(efficiencies):
    """Number of efficiencies, their mean, its standard error and their
    standard deviation."""
    count = len(efficiencies)
    if count < 2:
        raise TooFewValues(f"{count} events in the point, a mean and a spread need at least 2")
    spread = float(np.std(efficiencies, ddof=1))
    return {
        "events": count,
        "mean": float(np.mean(efficiencies)),
        "mean_error": spread / np.sqrt(count),
        "spread": spread,
    }


def energy_resolution(values):
    """What `mad_core_resolution` gives for the values of a quantity of the
    events of a point, or `events` and `error` in place of it when the values
    give no width."""
    try:
        return mad_core_resolution(values)
    except (TooFewValues, NoSpread) as no_width:
        return {"events": len(values), "error": str(no_width)}
