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
    e         deposited energy [MeV]; of a laser, the pairs times the pair
              energy of the material, not the energy of the absorbed light
    pairs     electron-hole pairs the deposit created

Attributes of the file: generated_events, the events the source generated;
recorded_events, those of them the file holds; generated_fraction, the part
of what the source emits that was generated, such as the directions within
the cone of a radioactive source (1 for a beam or a toy MIP, which emit
nothing else); require, the logic expression over the slots that an event
satisfies to be recorded; coincidence_window_ns, its window in time [ns],
where there is one; and edep_min.<slot>, edep_max.<slot> [MeV], the window
of the energy deposited in the slot, where it has that bound. The share of
the generated events that was recorded is not generated_fraction but
recorded_events / generated_events; the events recorded per emission of the source are recorded_events / generated_events
* generated_fraction.
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
    # slot -> (edep_min, edep_max) [MeV] of the energy deposited in the slot;
    # None: that side is not checked
    windows: dict[str, tuple[float | None, float | None]]
    # logic expression over the slots, and its window in time [ns]; None: any time
    require: str
    coincidence_window_ns: float | None
    events: list[EventDeposits]
    # the part of what the source emits that was generated
    generated_fraction: float = 1.0


def deposits_of_steps(
    detector: str,
    event_numbers,
    positions,
    energies,
    times,
    starts=None,
) -> list[EventDeposits]:
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
    return events


def joined(per_detector: list[list[EventDeposits]]) -> list[EventDeposits]:
    """The events of several detectors as one list: an event that more than
    one detector has takes the deposits of the detectors one after another,
    in the order of `per_detector`. The events are in the order of their
    numbers."""
    by_number: dict[int, EventDeposits] = {}
    for events in per_detector:
        for event in events:
            if event.event not in by_number:
                by_number[event.event] = event
                continue
            into = by_number[event.event]
            for name in ("detector", *_NUMBERS):
                getattr(into, name).extend(getattr(event, name))
            for name in _STARTS:
                if getattr(into, name) is not None:
                    getattr(into, name).extend(getattr(event, name))
    return [by_number[number] for number in sorted(by_number)]


def write_deposits(path: str, deposits: Deposits) -> None:
    """Write `deposits` to the file at `path`, replacing it. The events are
    checked first: a column that does not hold one value for each deposit of
    its event, an event without pairs, and starts or time spreads that some
    events have and others lack are errors, and the file is left as it was."""
    events = deposits.events
    optional = [
        name
        for name in (*_STARTS, "t_fwhm")
        if events and all(getattr(record, name) is not None for record in events)
    ]
    for name in (*_STARTS, "t_fwhm"):
        given = [getattr(record, name) is not None for record in events]
        if any(given) and not all(given):
            raise ValueError(f"some events have {name} and some do not")
    for record in events:
        if record.pairs is None:
            raise ValueError(
                f"event {record.event} has no electron-hole pairs: "
                "only deposits whose ionization was drawn are written"
            )
        for name in ("detector", *_NUMBERS, "pairs", *optional):
            if len(getattr(record, name)) != len(record.e):
                raise ValueError(
                    f"event {record.event} has {len(record.e)} deposits and "
                    f"{len(getattr(record, name))} values of {name}"
                )
    with h5py.File(str(path), "w") as file:
        file.attrs["generated_events"] = deposits.generated_events
        file.attrs["recorded_events"] = len(events)
        file.attrs["generated_fraction"] = deposits.generated_fraction
        file.attrs["require"] = deposits.require
        if deposits.coincidence_window_ns is not None:
            file.attrs["coincidence_window_ns"] = deposits.coincidence_window_ns
        for slot, bounds in deposits.windows.items():
            for name, bound in zip(("edep_min", "edep_max"), bounds):
                if bound is not None:
                    file.attrs[f"{name}.{slot}"] = bound
        file["event"] = np.array([record.event for record in events], dtype="int64")
        file["count"] = np.array([len(record.e) for record in events], dtype="int64")
        file.create_dataset(
            "detector",
            data=[name for record in events for name in record.detector],
            dtype=h5py.string_dtype(),
        )
        for name in (*_NUMBERS, "pairs", *optional):
            file[name] = np.array(
                [value for record in events for value in getattr(record, name)],
                dtype="float64",
            )


def read_deposits(path: str) -> Deposits:
    with h5py.File(str(path), "r") as file:
        generated_events = int(file.attrs["generated_events"])
        generated_fraction = float(file.attrs["generated_fraction"])
        require = str(file.attrs["require"])
        window = file.attrs.get("coincidence_window_ns")
        coincidence_window_ns = None if window is None else float(window)
        windows: dict[str, list[float | None]] = {}
        for key in file.attrs:
            name, _, slot = key.partition(".")
            if name in ("edep_min", "edep_max"):
                windows.setdefault(slot, [None, None])[name == "edep_max"] = float(file.attrs[key])
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
    return Deposits(
        generated_events,
        {slot: (bounds[0], bounds[1]) for slot, bounds in windows.items()},
        require,
        coincidence_window_ns,
        events,
        generated_fraction,
    )
