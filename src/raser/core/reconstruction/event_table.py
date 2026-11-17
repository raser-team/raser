"""Every event of a job as one row: what its waveforms give, and its file.

The file is HDF5, one per job, and is written at once.

Attributes of the file:
    electrodes           names of the electrodes, in the order of the columns
    threshold            of the times and the area [V], above the baseline
    amplitude_threshold  of the selected events [V], above the baseline
    fractions            of the constant-fraction times, (fractions,)
    edge                 for each electrode, "rising" or "falling": the edge
                         the thresholds are set on, as on a scope; a falling
                         pulse is turned positive before its quantities are
                         taken
Datasets, one row per event of the readout file:
    event           Geant4 event number
    selected        the amplitude of one of its electrodes at least is not
                    below amplitude_threshold: it has a cluster
    cluster_size    electrodes of its cluster, 0 when it has none
    cluster_center  amplitude-weighted place of the cluster, in electrodes
                    from the first one; NaN when it has none
Datasets, one row per event and one column per electrode:
    traced          the readout holds a waveform of the electrode in the
                    event; one without has NaN in the columns below and is
                    not above
    baseline        mean of the samples before the pulse [V]
    noise           their standard deviation [V]
    amplitude       largest sample above the baseline [V]
    above           amplitude is not below threshold
    ToA             where the rising edge crosses threshold [s]
    ToT             from there to where the falling edge crosses it [s];
                    0 when it does not fall below it before the record ends
    CoG             centre of gravity in time of the part above threshold [s]
    area            integral of the lobe of the pulse that holds its peak:
                    the bins on either side of the peak down to where the
                    pulse returns to the baseline [V s]
Dataset, one row per event, one column per electrode and one per fraction:
    CFD             where the rising edge crosses the fraction of the
                    amplitude [s]
The times, CoG and area are NaN where `above` is false, and a time is NaN
where its crossing is not found.
"""

from __future__ import annotations

from dataclasses import dataclass

import h5py
import numpy as np

from .event import get_amplitude
from .event import get_CFD50
from .event import get_CoG
from .event import get_ToA
from .event import get_ToT
from .event import net_pulse

ELECTRODE_COLUMNS = ("traced", "baseline", "noise", "amplitude", "above", "ToA", "ToT", "CoG", "area")
EVENT_COLUMNS = ("event", "selected", "cluster_size", "cluster_center")
EDGE_SIGN = {"rising": 1.0, "falling": -1.0}
KINDS = {"event": "int64", "selected": "bool", "traced": "bool", "above": "bool", "cluster_size": "int64"}


@dataclass
class EventTable:
    electrodes: list[str]
    threshold: float  # [V]
    amplitude_threshold: float  # [V]
    fractions: tuple[float, ...]
    edges: list[str]  # of each electrode
    # each name of EVENT_COLUMNS, ELECTRODE_COLUMNS and "CFD" to its array
    columns: dict[str, np.ndarray]

    def __len__(self) -> int:
        return len(self.columns["event"])


def lobe_area(samples, peak, dt):
    """Integral of the positive lobe that holds the bin `peak`: from the bin
    after the last one not above zero before it, to the bin before the
    first one not above zero after it [unit of the samples times s]."""
    first = peak
    while first > 0 and samples[first - 1] > 0:
        first -= 1
    last = peak
    while last < len(samples) - 1 and samples[last + 1] > 0:
        last += 1
    return float(np.sum(samples[first:last + 1]) * dt)


def electrode_row(times, dt, net, threshold, fractions):
    """What one positive waveform without its baseline gives, as the
    columns of one electrode of ELECTRODE_COLUMNS from amplitude to area
    and the times of the fractions."""
    amplitude, peak = get_amplitude(net)
    nothing = float("nan")
    if amplitude < threshold:
        return {"amplitude": amplitude, "above": False, "ToA": nothing, "ToT": nothing,
                "CoG": nothing, "area": nothing}, [nothing] * len(fractions)
    arrival = get_ToA(times, net, threshold, peak)
    row = {
        "amplitude": amplitude,
        "above": True,
        "ToA": nothing if arrival is None else arrival,
        "ToT": get_ToT(times, net, threshold, peak),
        "CoG": get_CoG(times, net, threshold, peak),
        "area": lobe_area(net, peak, dt),
    }
    constant = [get_CFD50(times, net, part, peak) for part in fractions]
    return row, [nothing if time is None else time for time in constant]


def cluster(amplitudes, threshold, amplitude_threshold):
    """Size and amplitude-weighted centre of the cluster of one event: the
    electrodes whose amplitude is not below the amplitude threshold, and
    their neighbours whose amplitude is not below the threshold. All of them
    make one cluster. (0, NaN) when no electrode reaches the amplitude
    threshold."""
    seeds = [k for k, amplitude in enumerate(amplitudes) if amplitude >= amplitude_threshold]
    members = sorted(
        {j for k in seeds for j in (k - 1, k, k + 1) if j == k or (0 <= j < len(amplitudes) and amplitudes[j] >= threshold)}
    )
    if not members:
        return 0, float("nan")
    weights = np.array([amplitudes[j] for j in members], dtype="float64")
    return len(members), float(np.dot(members, weights) / weights.sum())


def chosen_edges(given, derived, electrodes):
    """The edge the thresholds are set on for each electrode, and a line for
    each electrode whose given edge is not the one its pulse has.

    given : "rising", "falling" or None
    derived : the edge of the pulse of each electrode, as the readout
        derives it from the device and the chain
    None takes the derived edges; a given edge holds for every electrode.
    """
    if given is None:
        return list(derived), []
    if given not in EDGE_SIGN:
        raise ValueError(
            f"edge {given!r}: the thresholds are set on a rising (positive pulses) "
            "or a falling (negative pulses) edge"
        )
    notes = [
        f"edge {given} given for {name}, whose pulse is {edge}: its pulses are not seen as the readout makes them"
        for name, edge in zip(electrodes, derived)
        if edge != given
    ]
    return [given] * len(electrodes), notes


def event_table(waveforms, threshold, amplitude_threshold, fractions, edges):
    """The rows of the events of one job.

    waveforms : the readout of the job, as `read_waveforms` gives it; an
        event may hold the waveforms of some of its electrodes only
    threshold, amplitude_threshold : in the unit of the waveforms [V]
    edges : "rising" or "falling" for each electrode, as `chosen_edges`
        gives them
    """
    if len(edges) != len(waveforms.electrodes) or any(edge not in EDGE_SIGN for edge in edges):
        raise ValueError(f"edges {edges}: one of rising or falling for each of {waveforms.electrodes}")
    polarity = [EDGE_SIGN[edge] for edge in edges]
    place = {name: k for k, name in enumerate(waveforms.electrodes)}
    wrong = [part for part in fractions if not 0 < part < 1]
    if wrong:
        raise ValueError(f"fractions {wrong}: a constant fraction lies between 0 and 1")
    if not waveforms.events:
        raise ValueError("the readout holds no event")
    width = len(waveforms.electrodes)
    nothing = float("nan")
    columns: dict[str, list] = {name: [] for name in (*EVENT_COLUMNS, *ELECTRODE_COLUMNS, "CFD")}
    for record in waveforms.events:
        times = record.t0 + (np.arange(record.voltage.shape[1]) + 0.5) * waveforms.dt
        untraced = {"traced": False, "baseline": nothing, "noise": nothing, "amplitude": nothing, "above": False,
                    "ToA": nothing, "ToT": nothing, "CoG": nothing, "area": nothing}
        rows = [dict(untraced) for _ in range(width)]
        constant = [[nothing] * len(fractions) for _ in range(width)]
        for name, samples in zip(record.electrodes, record.voltage):
            k = place[name]
            net, baseline, noise = net_pulse(samples)
            row, constant[k] = electrode_row(times, waveforms.dt, polarity[k] * net, threshold, fractions)
            rows[k] = {**row, "traced": True, "baseline": baseline, "noise": noise}
        size, center = cluster([row["amplitude"] for row in rows], threshold, amplitude_threshold)
        columns["event"].append(record.event)
        columns["selected"].append(size > 0)
        columns["cluster_size"].append(size)
        columns["cluster_center"].append(center)
        for name in ELECTRODE_COLUMNS:
            columns[name].append([row[name] for row in rows])
        columns["CFD"].append(constant)
    arrays = {name: np.array(values, dtype=KINDS.get(name, "float64")) for name, values in columns.items()}
    arrays["CFD"] = arrays["CFD"].reshape(len(waveforms.events), width, len(fractions))
    return EventTable(
        list(waveforms.electrodes), float(threshold), float(amplitude_threshold),
        tuple(float(part) for part in fractions), list(edges), arrays,
    )


def write_event_table(path, table):
    with h5py.File(str(path), "w") as file:
        file.attrs.create("electrodes", table.electrodes, dtype=h5py.string_dtype())
        file.attrs["threshold"] = table.threshold
        file.attrs["amplitude_threshold"] = table.amplitude_threshold
        file.attrs["fractions"] = np.array(table.fractions, dtype="float64")
        file.attrs.create("edge", table.edges, dtype=h5py.string_dtype())
        for name, values in table.columns.items():
            file[name] = values


def read_event_table(path):
    with h5py.File(str(path), "r") as file:
        return EventTable(
            file.attrs["electrodes"].tolist(),
            float(file.attrs["threshold"]),
            float(file.attrs["amplitude_threshold"]),
            tuple(float(part) for part in file.attrs["fractions"]),
            file.attrs["edge"].tolist(),
            {name: file[name][()] for name in file},
        )
