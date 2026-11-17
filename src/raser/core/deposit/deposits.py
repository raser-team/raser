"""Energy deposits of a batch of events, and their file.

The file is HDF5. The deposits of all recorded events lie one after
another; ``count`` cuts them into events.

Datasets, one value per recorded event:
    event     Geant4 event number
    count     number of deposits of the event
Datasets, one value per deposit:
    detector  name of the detector the deposit lies in
    x, y, z   position in the coordinates of that detector [um]: the middle
              of the step that made the deposit
    x_start, y_start, z_start
              where that step starts [um]; it ends at 2 * (x, y, z) - start.
              A writer that does not know them leaves them out.
    t_fwhm    FWHM [s] of the Gaussian spread of the times, around t, at which
              the pairs of the deposit are made; without it they are made at t
    t         time since the primary was generated [s]
    e         deposited energy [MeV]
    pairs     electron-hole pairs the deposit created

Attributes of the file: generated_events, the events the source generated;
recorded_events, those of them the file holds; generated_fraction, the part
of what the source emits that was generated, such as the directions within
the cone of a radioactive source; and edep_min, edep_max [MeV] where the
window has that bound.
"""

from __future__ import annotations

from dataclasses import dataclass

import h5py
import numpy as np

_NUMBERS = ("x", "y", "z", "t", "e")
_STARTS = ("x_start", "y_start", "z_start")


@dataclass
class EventDeposits:
    event: int
    detector: list[str]
    x: list[float]
    y: list[float]
    z: list[float]
    t: list[float]
    e: list[float]
    # electron-hole pairs of every deposit; None until the ionization is drawn
    pairs: list[float] | None = None
    # where the step of every deposit starts [um]; None when it is not known
    x_start: list[float] | None = None
    y_start: list[float] | None = None
    z_start: list[float] | None = None
    # FWHM [s] of the times around t at which the pairs are made; None: at t
    t_fwhm: list[float] | None = None


@dataclass
class Deposits:
    generated_events: int
    edep_min: float | None
    edep_max: float | None
    events: list[EventDeposits]
    # the part of what the source emits that was generated
    generated_fraction: float = 1.0


def deposits_of_steps(
    detector: str,
    event_numbers,
    positions,
    energies,
    times,
    generated_events: int,
    edep_min: float | None,
    edep_max: float | None,
    starts=None,
) -> Deposits:
    """Deposits of one detector from the steps recorded event by event.

    positions[i][k] is the (x, y, z) [um] of step k of event i in the
    coordinates of the detector, energies[i][k] its energy [MeV] and
    times[i][k] its time [s], and starts[i][k], if given, where the step
    starts. Steps that deposit no energy are left out, and so are events left
    without a deposit.
    """
    events = []
    if starts is None:
        starts = [None] * len(positions)
    for number, event_positions, event_energies, event_times, event_starts in zip(
        event_numbers, positions, energies, times, starts, strict=True
    ):
        kept = [k for k, energy in enumerate(event_energies) if energy > 0]
        if not kept:
            continue
        begun = (
            {}
            if event_starts is None
            else {
                name: [float(event_starts[k][axis]) for k in kept]
                for axis, name in enumerate(("x_start", "y_start", "z_start"))
            }
        )
        events.append(
            EventDeposits(
                int(number),
                [detector] * len(kept),
                [float(event_positions[k][0]) for k in kept],
                [float(event_positions[k][1]) for k in kept],
                [float(event_positions[k][2]) for k in kept],
                [float(event_times[k]) for k in kept],
                [float(event_energies[k]) for k in kept],
                **begun,
            )
        )
    return Deposits(generated_events, edep_min, edep_max, events)


def write_deposits(path: str, deposits: Deposits) -> None:
    events = deposits.events
    for record in events:
        if record.pairs is None:
            raise ValueError(
                f"event {record.event} has no electron-hole pairs: "
                "only deposits whose ionization was drawn are written"
            )
    with h5py.File(str(path), "w") as file:
        file.attrs["generated_events"] = deposits.generated_events
        file.attrs["recorded_events"] = len(events)
        file.attrs["generated_fraction"] = deposits.generated_fraction
        for bound in ("edep_min", "edep_max"):
            if getattr(deposits, bound) is not None:
                file.attrs[bound] = getattr(deposits, bound)
        file["event"] = np.array([record.event for record in events], dtype="int64")
        file["count"] = np.array([len(record.e) for record in events], dtype="int64")
        file.create_dataset(
            "detector",
            data=[name for record in events for name in record.detector],
            dtype=h5py.string_dtype(),
        )
        for name in (*_NUMBERS, "pairs"):
            file[name] = np.array(
                [value for record in events for value in getattr(record, name)],
                dtype="float64",
            )
        begun = [record.x_start is not None for record in events]
        if any(begun) and not all(begun):
            raise ValueError("some events know where their steps start and some do not")
        spread = [record.t_fwhm is not None for record in events]
        if any(spread) and not all(spread):
            raise ValueError("some events spread the times of their pairs and some do not")
        if events and all(spread):
            file["t_fwhm"] = np.array(
                [value for record in events for value in record.t_fwhm], dtype="float64"
            )
        if events and all(begun):
            for name in _STARTS:
                file[name] = np.array(
                    [value for record in events for value in getattr(record, name)],
                    dtype="float64",
                )


def read_deposits(path: str) -> Deposits:
    with h5py.File(str(path), "r") as file:
        generated_events = int(file.attrs["generated_events"])
        generated_fraction = float(file.attrs["generated_fraction"])
        edep_min, edep_max = (
            float(file.attrs[bound]) if bound in file.attrs else None
            for bound in ("edep_min", "edep_max")
        )
        numbers = file["event"][()]
        counts = file["count"][()]
        detector = file["detector"].asstr()[()]
        columns = {name: file[name][()] for name in (*_NUMBERS, "pairs")}
        optional = {name: file[name][()] for name in (*_STARTS, "t_fwhm") if name in file}
    events = []
    first = 0
    for number, count in zip(numbers, counts, strict=True):
        last = first + int(count)
        events.append(
            EventDeposits(
                int(number),
                detector[first:last].tolist(),
                *(columns[name][first:last].tolist() for name in (*_NUMBERS, "pairs")),
                **{name: column[first:last].tolist() for name, column in optional.items()},
            )
        )
        first = last
    return Deposits(generated_events, edep_min, edep_max, events, generated_fraction)
