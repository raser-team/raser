"""Output waveforms of a batch of events, and their file.

The file is HDF5 and grows event by event. An event holds the waveforms of
the electrodes it has a signal on, its traces, which may be some of the
electrodes of the file only: the strips of a row the charge of the event
reaches. The traces of all events lie one after another, and the bins of
all traces; ``traces`` cuts them into events, ``count`` each trace into
its bins.

Attributes of the file:
    electrodes  names of all the electrodes it may hold traces of
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
    count       number of time bins of each trace of the event
    traces      number of traces of the event; 0 for an event with no signal
Dataset, one row per trace:
    electrode   number, from 0, of its electrode in electrodes
Dataset, one row per bin of each trace:
    voltage     output voltage at the centre of the bin [V]
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
    voltage: np.ndarray  # (electrodes of the event, bins) [V]
    # names of the electrodes of the rows of voltage; None, in writing, for
    # all the electrodes of the file
    electrodes: list[str] | None = None


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

    electrodes : all the electrodes the file may hold traces of.
    record : EventWaveforms; its electrodes, some of electrodes or None for
        all of them, name the rows of its voltage.
    pulse_edge : what is written as ``pulse_edge`` when the file is created,
        one of "rising" and "falling" for each electrode; None writes none.
    circuit_values : what is written as ``device_circuit`` when the file is
        created; None writes none.
    """
    electrodes = list(electrodes)
    names = electrodes if record.electrodes is None else list(record.electrodes)
    unknown = sorted(set(names) - set(electrodes))
    if unknown or len(set(names)) != len(names):
        raise ValueError(
            f"the event {record.event} has traces of {names}, not each once of "
            f"the electrodes {electrodes}"
        )
    voltage = np.asarray(record.voltage, dtype="float64")
    if voltage.ndim != 2 or voltage.shape[0] != len(names):
        raise ValueError(
            f"voltage has shape {voltage.shape}, expected ({len(names)}, bins)"
        )

    if pulse_edge is not None and (
        len(pulse_edge) != len(electrodes)
        or not set(pulse_edge) <= {"rising", "falling"}
    ):
        raise ValueError(
            f"pulse_edge {list(pulse_edge)} is not one of rising and falling "
            f"for each of the electrodes {electrodes}"
        )
    new = not os.path.exists(path)
    with h5py.File(str(path), "a") as file:
        if new:
            file.attrs.create("electrodes", electrodes, dtype=h5py.string_dtype())
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
                ("traces", "int64"),
                ("electrode", "int64"),
            ):
                file.create_dataset(name, shape=(0,), maxshape=(None,), dtype=kind)
            file.create_dataset(
                "voltage",
                shape=(0,),
                maxshape=(None,),
                dtype="float64",
                compression="gzip",
            )
        else:
            in_file = file.attrs["electrodes"].tolist()
            if in_file != electrodes or float(file.attrs["dt"]) != float(dt):
                raise ValueError(
                    f"{path} holds waveforms of electrodes {in_file} with dt "
                    f"{float(file.attrs['dt'])} s, not of {electrodes} with "
                    f"dt {dt} s"
                )
        rows = {
            "event": np.array([int(record.event)]),
            "t0": np.array([float(record.t0)]),
            "count": np.array([voltage.shape[1]]),
            "traces": np.array([len(names)]),
            "electrode": np.array(
                [electrodes.index(name) for name in names], dtype="int64"
            ),
            "voltage": voltage.reshape(-1),
        }
        for name, values in rows.items():
            dataset = file[name]
            first = dataset.shape[0]
            dataset.resize(first + len(values), axis=0)
            dataset[first:] = values


def read_waveforms(path):
    """Waveforms of the file, each event with the names of its traces."""
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
        traces = file["traces"][()]
        of_trace = file["electrode"][()]
        voltage = file["voltage"][()]
    events = []
    trace, sample = 0, 0
    for number, start, count, many in zip(numbers, starts, counts, traces, strict=True):
        size = int(many) * int(count)
        events.append(
            EventWaveforms(
                int(number),
                float(start),
                voltage[sample : sample + size].reshape(int(many), int(count)),
                [electrodes[k] for k in of_trace[trace : trace + int(many)]],
            )
        )
        trace, sample = trace + int(many), sample + size
    return Waveforms(electrodes, dt, events, pulse_edge)


def read_circuit_values(path):
    """``device_circuit`` of the file; None when it has none."""
    with h5py.File(str(path), "r") as file:
        if "device_circuit" not in file.attrs:
            return None
        return json.loads(file.attrs["device_circuit"])
