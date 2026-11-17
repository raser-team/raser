"""Output waveforms of a batch of events, and their file.

The file is HDF5 and grows event by event. The bins of all events lie one
after another; ``count`` cuts them into events.

Attributes of the file:
    electrodes  names of the electrodes, in the order of the columns
    dt          width of a time bin [s]
    pulse_edge  for each electrode, in their order, "rising" or "falling":
                which way its pulse goes, as the device and the chain make
                it; the readout writes it, and a file without it is not read
    device_circuit
                values the circuit of the device is made of and where each
                is from, as JSON; not there when none were given
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
    pulse_edge: list[str]


def append_waveforms(
    path, electrodes, dt, record, circuit_values=None, pulse_edge=None
):
    """Add one event to the file, which is created with the first event.

    pulse_edge : what is written as ``pulse_edge`` when the file is created,
        one of "rising" and "falling" for each electrode; None writes none.

    circuit_values : what is written as ``device_circuit`` when the file is created;
        None writes none.
    """
    voltage = np.asarray(record.voltage, dtype="float64")
    if voltage.ndim != 2 or voltage.shape[0] != len(electrodes):
        raise ValueError(
            f"voltage has shape {voltage.shape}, expected ({len(electrodes)}, bins)"
        )

    if pulse_edge is not None and (
        len(pulse_edge) != len(electrodes)
        or not set(pulse_edge) <= {"rising", "falling"}
    ):
        raise ValueError(
            f"pulse_edge {list(pulse_edge)} is not one of rising and falling "
            f"for each of the electrodes {list(electrodes)}"
        )
    new = not os.path.exists(path)
    with h5py.File(str(path), "a") as file:
        if new:
            file.attrs.create("electrodes", list(electrodes), dtype=h5py.string_dtype())
            file.attrs["dt"] = float(dt)
            if circuit_values is not None:
                file.attrs["device_circuit"] = json.dumps(circuit_values)
            if pulse_edge is not None:
                file.attrs.create(
                    "pulse_edge", list(pulse_edge), dtype=h5py.string_dtype()
                )
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
        if "pulse_edge" not in file.attrs:
            raise ValueError(
                f"{path} has no pulse_edge: the readout of this version did "
                "not write it; run the readout again"
            )
        pulse_edge = file.attrs["pulse_edge"].tolist()
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
    return Waveforms(electrodes, dt, events, pulse_edge)


def read_circuit_values(path):
    """``device_circuit`` of the file; None when it has none."""
    with h5py.File(str(path), "r") as file:
        if "device_circuit" not in file.attrs:
            return None
        return json.loads(file.attrs["device_circuit"])
