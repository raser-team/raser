"""Induced currents of a batch of events, and their file.

The file is HDF5 and grows event by event. The bins of all events lie one
after another; ``count`` cuts them into events.

Attributes of the file:
    electrodes  names of the electrodes, in the order of the columns
    dt          width of a time bin [s]
Datasets, one row per event:
    event       Geant4 event number
    t0          left edge of the first time bin of the event [s]
    count       number of time bins of the event
    charge      signed net charge of each electrode [C]
Dataset, one row per time bin:
    current     mean current of each electrode in the bin [A]
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import h5py
import numpy as np


@dataclass
class EventCurrents:
    event: int
    t0: float
    current: np.ndarray  # (electrodes, bins) [A]
    charge: np.ndarray  # (electrodes,) [C]


@dataclass
class Currents:
    electrodes: list[str]
    dt: float
    events: list[EventCurrents]


def append_currents(path, electrodes: list[str], dt: float, record: EventCurrents) -> None:
    """Add one event to the file, which is created with the first event."""
    current = np.asarray(record.current, dtype="float64")
    charge = np.asarray(record.charge, dtype="float64")
    if current.ndim != 2 or current.shape[0] != len(electrodes):
        raise ValueError(
            f"current has shape {current.shape}, expected ({len(electrodes)}, bins)"
        )
    if charge.shape != (len(electrodes),):
        raise ValueError(f"charge has shape {charge.shape}, expected ({len(electrodes)},)")

    new = not os.path.exists(path)
    with h5py.File(str(path), "a") as file:
        if new:
            file.attrs.create("electrodes", list(electrodes), dtype=h5py.string_dtype())
            file.attrs["dt"] = float(dt)
            for name, kind in (("event", "int64"), ("t0", "float64"), ("count", "int64")):
                file.create_dataset(name, shape=(0,), maxshape=(None,), dtype=kind)
            for name in ("charge", "current"):
                file.create_dataset(
                    name,
                    shape=(0, len(electrodes)),
                    maxshape=(None, len(electrodes)),
                    dtype="float64",
                    compression="gzip",
                )
        else:
            in_file = file.attrs["electrodes"].tolist()
            if in_file != list(electrodes) or float(file.attrs["dt"]) != float(dt):
                raise ValueError(
                    f"{path} holds currents of electrodes {in_file} with dt "
                    f"{float(file.attrs['dt'])} s, not of {list(electrodes)} with dt {dt} s"
                )
        rows = {
            "event": [int(record.event)],
            "t0": [float(record.t0)],
            "count": [current.shape[1]],
            "charge": charge[None, :],
            "current": current.T,
        }
        for name, values in rows.items():
            dataset = file[name]
            first = dataset.shape[0]
            dataset.resize(first + len(values), axis=0)
            dataset[first:] = values


def read_currents(path) -> Currents:
    with h5py.File(str(path), "r") as file:
        electrodes = file.attrs["electrodes"].tolist()
        dt = float(file.attrs["dt"])
        numbers = file["event"][()]
        starts = file["t0"][()]
        counts = file["count"][()]
        charges = file["charge"][()]
        current = file["current"][()]
    events = []
    first = 0
    for number, start, count, charge in zip(numbers, starts, counts, charges, strict=True):
        last = first + int(count)
        events.append(EventCurrents(int(number), float(start), current[first:last].T, charge))
        first = last
    return Currents(electrodes, dt, events)
