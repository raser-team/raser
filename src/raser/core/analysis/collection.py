"""Charge collection efficiency of events."""

import numpy as np

ELEMENTARY_CHARGE = 1.602176634e-19  # C


def collection_efficiency(charge, pairs):
    """Net charge of all read-out electrodes together over the charge of the
    pairs of the event, without sign: the carrier the electrodes collect does
    not matter.

    charge : (events, electrodes), signed net charge [C]
    pairs  : (events,), electron-hole pairs of each event before gain

    Returns (events,). Gain makes it larger than 1.
    """
    charge = np.asarray(charge, dtype="float64")
    pairs = np.asarray(pairs, dtype="float64")
    if charge.ndim != 2 or pairs.shape != charge.shape[:1]:
        raise ValueError(
            f"charge has shape {charge.shape} and pairs {pairs.shape}, "
            "expected (events, electrodes) and (events,)"
        )
    if np.any(pairs <= 0):
        raise ValueError(f"events {np.flatnonzero(pairs <= 0).tolist()} have no pairs")
    return np.abs(charge.sum(axis=1)) / (pairs * ELEMENTARY_CHARGE)
