"""Induced currents of a batch of events, and their file.

The file is HDF5 and grows event by event. Of an event only the electrodes
whose current is not zero throughout are stored: ``stored`` cuts ``index``
into events, and every stored electrode has the ``count`` bins of its event
in ``current``, one stored electrode after another.

Attributes of the file:
    electrodes  names of the electrodes, in the order of the columns
    dt          width of a time bin [s]
Datasets, one row per event:
    event       Geant4 event number
    t0          left edge of the first time bin of the event [s]
    count       number of time bins of the event
    pairs       electron-hole pairs the event gave to the current, before gain
    sensitive_pairs  of those, the pairs born where the device does not
                conduct, which the drift moves; only in files written from
                a drift in a solved field
    carriers_without_field  carriers, without sign and not yet trapped,
                of the clusters that stopped where the field has no value:
                the current they would have induced further on is missing;
                0 for a whole event; only in files written from a drift
    charge      signed net charge of each electrode [C]
    stored      number of electrodes of the event that are stored
Dataset, one value per stored electrode:
    index       its place among the electrodes, from 0
Dataset, one value per time bin of a stored electrode:
    current     mean current of the electrode in the bin [A]
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
    pairs: float  # electron-hole pairs before gain
    # of those, the pairs born where the device does not conduct; None where
    # the currents do not come from a drift in a solved field
    sensitive_pairs: float | None = None
    # carriers of the clusters that stopped where the field has no value,
    # as they were when they stopped; None as sensitive_pairs
    carriers_without_field: float | None = None


# the numbers of an event that only a drift in a solved field gives
_OF_A_DRIFT = ("sensitive_pairs", "carriers_without_field")


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
        for name in _OF_A_DRIFT:
            value = getattr(record, name)
            if new and value is not None:
                file.create_dataset(name, shape=(0,), maxshape=(None,), dtype="float64")
            if (name in file) != (value is not None):
                raise ValueError(
                    f"{path} {'holds' if name in file else 'does not hold'} {name}, "
                    f"the event {record.event} {'has none' if value is None else 'has it'}"
                )
        if new:
            file.attrs.create("electrodes", list(electrodes), dtype=h5py.string_dtype())
            file.attrs["dt"] = float(dt)
            for name, kind in (
                ("event", "int64"),
                ("t0", "float64"),
                ("count", "int64"),
                ("pairs", "float64"),
                ("stored", "int64"),
                ("index", "int64"),
            ):
                file.create_dataset(name, shape=(0,), maxshape=(None,), dtype=kind)
            file.create_dataset(
                "charge",
                shape=(0, len(electrodes)),
                maxshape=(None, len(electrodes)),
                dtype="float64",
                compression="gzip",
            )
            file.create_dataset(
                "current", shape=(0,), maxshape=(None,), dtype="float64", compression="gzip"
            )
        else:
            in_file = file.attrs["electrodes"].tolist()
            if in_file != list(electrodes) or float(file.attrs["dt"]) != float(dt):
                raise ValueError(
                    f"{path} holds currents of electrodes {in_file} with dt "
                    f"{float(file.attrs['dt'])} s, not of {list(electrodes)} with dt {dt} s"
                )
        stored = np.flatnonzero(current.any(axis=1))
        rows = {
            "event": [int(record.event)],
            "t0": [float(record.t0)],
            "count": [current.shape[1]],
            "pairs": [float(record.pairs)],
            "charge": charge[None, :],
            "stored": [len(stored)],
            "index": stored,
            "current": current[stored].ravel(),
        }
        for name in _OF_A_DRIFT:
            if getattr(record, name) is not None:
                rows[name] = [float(getattr(record, name))]
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
        pairs = file["pairs"][()]
        charges = file["charge"][()]
        stored = file["stored"][()]
        index = file["index"][()]
        values = file["current"][()]
        sensitive, without_field = (
            file[name][()] if name in file else [None] * len(numbers) for name in _OF_A_DRIFT
        )
    events = []
    first_electrode = 0
    first_value = 0
    for number, start, count, charge, n_pairs, n_stored, n_sensitive, n_without_field in zip(
        numbers, starts, counts, charges, pairs, stored, sensitive, without_field, strict=True
    ):
        last_electrode = first_electrode + int(n_stored)
        last_value = first_value + int(n_stored) * int(count)
        current = np.zeros((len(electrodes), int(count)))
        current[index[first_electrode:last_electrode]] = values[first_value:last_value].reshape(
            int(n_stored), int(count)
        )
        events.append(
            EventCurrents(
                int(number), float(start), current, charge, float(n_pairs),
                None if n_sensitive is None else float(n_sensitive),
                None if n_without_field is None else float(n_without_field),
            )
        )
        first_electrode, first_value = last_electrode, last_value
    return Currents(electrodes, dt, events)
