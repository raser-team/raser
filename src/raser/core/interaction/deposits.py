"""Energy deposits of a batch of events, and their file.

The file is a ROOT file with a TTree ``deposits``, one entry per recorded
event, and a TNamed ``generation`` whose title is JSON.

Branches of ``deposits``, the vectors aligned deposit by deposit:
    event     Geant4 event number
    detector  name of the detector the deposit lies in
    x, y, z   position in the coordinates of that detector [um]
    t         time since the primary was generated [s]
    e         deposited energy [MeV]

``generation``: generated_events, edep_min [MeV], edep_max [MeV].
"""

from __future__ import annotations

import json
from array import array
from dataclasses import dataclass

import ROOT

ROOT.gROOT.SetBatch(True)

_VECTORS = {
    "detector": "string",
    "x": "double",
    "y": "double",
    "z": "double",
    "t": "double",
    "e": "double",
}


@dataclass
class EventDeposits:
    event: int
    detector: list[str]
    x: list[float]
    y: list[float]
    z: list[float]
    t: list[float]
    e: list[float]


@dataclass
class Deposits:
    generated_events: int
    edep_min: float | None
    edep_max: float | None
    events: list[EventDeposits]


def deposits_of_steps(
    detector: str,
    event_numbers,
    positions,
    energies,
    times,
    generated_events: int,
    edep_min: float | None,
    edep_max: float | None,
) -> Deposits:
    """Deposits of one detector from the steps recorded event by event.

    positions[i][k] is the (x, y, z) [um] of step k of event i in the
    coordinates of the detector, energies[i][k] its energy [MeV] and
    times[i][k] its time [s]. Steps that deposit no energy are left out,
    and so are events left without a deposit.
    """
    events = []
    for number, event_positions, event_energies, event_times in zip(
        event_numbers, positions, energies, times, strict=True
    ):
        kept = [k for k, energy in enumerate(event_energies) if energy > 0]
        if not kept:
            continue
        events.append(
            EventDeposits(
                int(number),
                [detector] * len(kept),
                [float(event_positions[k][0]) for k in kept],
                [float(event_positions[k][1]) for k in kept],
                [float(event_positions[k][2]) for k in kept],
                [float(event_times[k]) for k in kept],
                [float(event_energies[k]) for k in kept],
            )
        )
    return Deposits(generated_events, edep_min, edep_max, events)


def write_deposits(path: str, deposits: Deposits) -> None:
    file = ROOT.TFile(str(path), "RECREATE")
    tree = ROOT.TTree("deposits", "energy deposits of each recorded event")
    event = array("q", [0])
    tree.Branch("event", event, "event/L")
    vectors = {name: ROOT.std.vector(kind)() for name, kind in _VECTORS.items()}
    for name, vector in vectors.items():
        tree.Branch(name, vector)
    for record in deposits.events:
        event[0] = record.event
        for name, vector in vectors.items():
            vector.clear()
            for value in getattr(record, name):
                vector.push_back(value)
        tree.Fill()
    tree.Write()
    generation = {
        "generated_events": deposits.generated_events,
        "edep_min": deposits.edep_min,
        "edep_max": deposits.edep_max,
    }
    ROOT.TNamed("generation", json.dumps(generation)).Write()
    file.Close()


def read_deposits(path: str) -> Deposits:
    file = ROOT.TFile(str(path), "READ")
    generation = json.loads(file.Get("generation").GetTitle())
    events = [
        EventDeposits(
            int(entry.event),
            [str(name) for name in entry.detector],
            list(entry.x),
            list(entry.y),
            list(entry.z),
            list(entry.t),
            list(entry.e),
        )
        for entry in file.Get("deposits")
    ]
    file.Close()
    return Deposits(
        generation["generated_events"],
        generation["edep_min"],
        generation["edep_max"],
        events,
    )
