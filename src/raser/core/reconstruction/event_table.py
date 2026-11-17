"""Every event of a job as one row: what its waveforms give, and its file.

The file is HDF5, one per job, and is written at once.

Attributes of the file:
    electrodes           names of the electrodes, in the order of the columns
    threshold            of the times and the charge [V], above the baseline
    amplitude_threshold  of the selected events [V], above the baseline
    fractions            of the constant-fraction times, (fractions,)
    edge                 "rising" or "falling": the edge the thresholds are
                         set on, as on a scope; a falling pulse is turned
                         positive before its quantities are taken
Datasets, one row per event of the readout file:
    event           Geant4 event number
    selected        its largest amplitude above threshold is not below
                    amplitude_threshold
    cluster_size    electrodes of its cluster, 0 when it has none
    cluster_center  amplitude-weighted place of the cluster, in electrodes
                    from the first one; NaN when it has none
Datasets, one row per event and one column per electrode:
    baseline        mean of the samples before the pulse [V]
    noise           their standard deviation [V]
    amplitude       largest sample above the baseline [V]
    above           amplitude is not below threshold
    ToA             where the rising edge crosses threshold [s]
    ToT             from there to where the falling edge crosses it [s];
                    0 when it does not fall below it before the record ends
    CoG             centre of gravity in time of the part above threshold [s]
    charge          integral of the waveform above the baseline [V s]
Dataset, one row per event, one column per electrode and one per fraction:
    CFD             where the rising edge crosses the fraction of the
                    amplitude [s]
The times, CoG and charge are NaN where `above` is false, and a time is NaN
where its crossing is not found.
"""

from __future__ import annotations

from dataclasses import dataclass

import h5py
import numpy as np

from .event import get_amplitude
from .event import get_CFD50
from .event import get_CoG
from .event import get_gravity_center_and_cluster_size
from .event import get_ToA
from .event import get_ToT
from .event import net_pulse

ELECTRODE_COLUMNS = ("baseline", "noise", "amplitude", "above", "ToA", "ToT", "CoG", "charge")
EVENT_COLUMNS = ("event", "selected", "cluster_size", "cluster_center")
EDGE_SIGN = {"rising": 1.0, "falling": -1.0}
KINDS = {"event": "int64", "selected": "bool", "above": "bool", "cluster_size": "int64"}


@dataclass
class EventTable:
    electrodes: list[str]
    threshold: float  # [V]
    amplitude_threshold: float  # [V]
    fractions: tuple[float, ...]
    edge: str
    # each name of EVENT_COLUMNS, ELECTRODE_COLUMNS and "CFD" to its array
    columns: dict[str, np.ndarray]

    def __len__(self) -> int:
        return len(self.columns["event"])


def electrode_row(times, dt, net, threshold, fractions):
    """What one positive waveform without its baseline gives, as the
    columns of one electrode of ELECTRODE_COLUMNS from amplitude to charge
    and the times of the fractions."""
    amplitude, peak = get_amplitude(net)
    nothing = float("nan")
    if amplitude < threshold:
        return {"amplitude": amplitude, "above": False, "ToA": nothing, "ToT": nothing,
                "CoG": nothing, "charge": nothing}, [nothing] * len(fractions)
    arrival = get_ToA(times, net, threshold, peak)
    row = {
        "amplitude": amplitude,
        "above": True,
        "ToA": nothing if arrival is None else arrival,
        "ToT": get_ToT(times, net, threshold, peak),
        "CoG": get_CoG(times, net, threshold, peak),
        "charge": float(np.sum(np.abs(net)) * dt),
    }
    constant = [get_CFD50(times, net, part, peak) for part in fractions]
    return row, [nothing if time is None else time for time in constant]


def cluster(amplitudes, above, amplitude_threshold):
    """Size and amplitude-weighted centre of the cluster of one event: the
    electrodes above the amplitude threshold and their neighbours above the
    threshold. (0, NaN) when no electrode is above the amplitude threshold."""
    weights = [float(amplitude) if is_above else 0.0 for amplitude, is_above in zip(amplitudes, above)]
    center, size = get_gravity_center_and_cluster_size(weights, amplitude_threshold)
    return size, float("nan") if center is None else float(center)


def event_table(waveforms, threshold, amplitude_threshold, fractions, edge):
    """The rows of the events of one job.

    waveforms : the readout of the job, as `read_waveforms` gives it
    threshold, amplitude_threshold : in the unit of the waveforms [V]
    edge : "rising" or "falling", the edge of the pulses the thresholds
        are set on
    """
    if edge not in EDGE_SIGN:
        raise ValueError(
            f"edge {edge!r}: give the edge the thresholds are set on, "
            "rising (positive pulses) or falling (negative pulses)"
        )
    polarity = EDGE_SIGN[edge]
    if not waveforms.events:
        raise ValueError("the readout holds no event")
    nets = [[net_pulse(samples) for samples in record.voltage] for record in waveforms.events]
    width = len(waveforms.electrodes)
    columns: dict[str, list] = {name: [] for name in (*EVENT_COLUMNS, *ELECTRODE_COLUMNS, "CFD")}
    for record, pulses in zip(waveforms.events, nets):
        times = record.t0 + (np.arange(record.voltage.shape[1]) + 0.5) * waveforms.dt
        rows, constant = [], []
        for net, _, _ in pulses:
            row, fraction_times = electrode_row(times, waveforms.dt, polarity * net, threshold, fractions)
            rows.append(row)
            constant.append(fraction_times)
        amplitudes = [row["amplitude"] for row in rows]
        above = [row["above"] for row in rows]
        size, center = cluster(amplitudes, above, amplitude_threshold)
        columns["event"].append(record.event)
        largest = max((value for value, is_above in zip(amplitudes, above) if is_above), default=None)
        columns["selected"].append(largest is not None and largest >= amplitude_threshold)
        columns["cluster_size"].append(size)
        columns["cluster_center"].append(center)
        columns["baseline"].append([baseline for _, baseline, _ in pulses])
        columns["noise"].append([noise for _, _, noise in pulses])
        for name in ("amplitude", "above", "ToA", "ToT", "CoG", "charge"):
            columns[name].append([row[name] for row in rows])
        columns["CFD"].append(constant)
    arrays = {name: np.array(values, dtype=KINDS.get(name, "float64")) for name, values in columns.items()}
    arrays["CFD"] = arrays["CFD"].reshape(len(waveforms.events), width, len(fractions))
    return EventTable(
        list(waveforms.electrodes), float(threshold), float(amplitude_threshold),
        tuple(float(part) for part in fractions), edge, arrays,
    )


def write_event_table(path, table):
    with h5py.File(str(path), "w") as file:
        file.attrs.create("electrodes", table.electrodes, dtype=h5py.string_dtype())
        file.attrs["threshold"] = table.threshold
        file.attrs["amplitude_threshold"] = table.amplitude_threshold
        file.attrs["fractions"] = np.array(table.fractions, dtype="float64")
        file.attrs["edge"] = table.edge
        for name, values in table.columns.items():
            file[name] = values


def read_event_table(path):
    with h5py.File(str(path), "r") as file:
        return EventTable(
            file.attrs["electrodes"].tolist(),
            float(file.attrs["threshold"]),
            float(file.attrs["amplitude_threshold"]),
            tuple(float(part) for part in file.attrs["fractions"]),
            str(file.attrs["edge"]),
            {name: file[name][()] for name in file},
        )
