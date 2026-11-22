"""The beam telescope: three reference layers, two devices under test and three reference layers.

One column along the beam in vacuum: the first layer 260 mm after the
source, then 40 mm from the back of each layer to the front of the next.
Reading it imports no Geant4."""

GAP_TO_FIRST = 260000  # um, from the source to the front of ref1
GAP = 40000  # um, from the back of a layer to the front of the next
SLOTS = ("ref1", "ref2", "ref3", "dut1", "dut2", "ref4", "ref5", "ref6")

G4SETUP = {
    "name": "telescope",
    "description": "Three reference layers, two devices under test and three reference layers along the beam, in vacuum",
    "geant4_model": "device",
    "world": "G4_Galactic",
    "maxstep": 2,
    "materials": {},
    "objects": {},
    "along_beam": [
        "source",
        {"gap": GAP_TO_FIRST},
        {"slot": SLOTS[0]},
        *[item for slot in SLOTS[1:] for item in ({"gap": GAP}, {"slot": slot})],
    ],
}
