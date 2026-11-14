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
