"""Output waveforms of a batch of events, and their file.

The file is HDF5 and grows event by event. The bins of all events lie one
after another; ``count`` cuts them into events.

Attributes of the file:
    electrodes  names of the electrodes, in the order of the columns
    dt          width of a time bin [s]
    sensor      values the circuit of the sensor is made of and where each is
                from, as JSON; not there when none were given
Datasets, one row per event:
    event       Geant4 event number
    t0          left edge of the first time bin of the event [s]
    count       number of time bins of the event
Dataset, one row per time bin:
    voltage     output voltage of each electrode at the centre of the bin [V]
"""

import json
import os
from dataclasses import dataclass

import h5py
import numpy as np


@dataclass
class EventWaveforms:
    event: int
    t0: float
    voltage: np.ndarray  # (electrodes, bins) [V]


@dataclass
class Waveforms:
    electrodes: list[str]
    dt: float
    events: list[EventWaveforms]


def append_waveforms(path, electrodes, dt, record, sensor_values=None):
    """Add one event to the file, which is created with the first event.

    sensor_values : what is written as ``sensor`` when the file is created;
        None writes none.
    """
    voltage = np.asarray(record.voltage, dtype="float64")
    if voltage.ndim != 2 or voltage.shape[0] != len(electrodes):
        raise ValueError(
            f"voltage has shape {voltage.shape}, expected ({len(electrodes)}, bins)"
        )

    new = not os.path.exists(path)
    with h5py.File(str(path), "a") as file:
        if new:
            file.attrs.create("electrodes", list(electrodes), dtype=h5py.string_dtype())
            file.attrs["dt"] = float(dt)
            if sensor_values is not None:
                file.attrs["sensor"] = json.dumps(sensor_values)
            for name, kind in (
                ("event", "int64"),
                ("t0", "float64"),
                ("count", "int64"),
            ):
                file.create_dataset(name, shape=(0,), maxshape=(None,), dtype=kind)
            file.create_dataset(
                "voltage",
                shape=(0, len(electrodes)),
                maxshape=(None, len(electrodes)),
                dtype="float64",
                compression="gzip",
            )
        else:
            in_file = file.attrs["electrodes"].tolist()
            if in_file != list(electrodes) or float(file.attrs["dt"]) != float(dt):
                raise ValueError(
                    f"{path} holds waveforms of electrodes {in_file} with dt "
                    f"{float(file.attrs['dt'])} s, not of {list(electrodes)} with "
                    f"dt {dt} s"
                )
        rows = {
            "event": np.array([int(record.event)]),
            "t0": np.array([float(record.t0)]),
            "count": np.array([voltage.shape[1]]),
            "voltage": voltage.T,
        }
        for name, values in rows.items():
            dataset = file[name]
            first = dataset.shape[0]
            dataset.resize(first + len(values), axis=0)
            dataset[first:] = values


def read_waveforms(path):
    """Waveforms of the file."""
    with h5py.File(str(path), "r") as file:
        electrodes = file.attrs["electrodes"].tolist()
        dt = float(file.attrs["dt"])
        numbers = file["event"][()]
        starts = file["t0"][()]
        counts = file["count"][()]
        voltage = file["voltage"][()]
    events = []
    first = 0
    for number, start, count in zip(numbers, starts, counts, strict=True):
        last = first + int(count)
        events.append(EventWaveforms(int(number), float(start), voltage[first:last].T))
        first = last
    return Waveforms(electrodes, dt, events)


def read_sensor_values(path):
    """``sensor`` of the file; None when it has none."""
    with h5py.File(str(path), "r") as file:
        if "sensor" not in file.attrs:
            return None
        return json.loads(file.attrs["sensor"])
