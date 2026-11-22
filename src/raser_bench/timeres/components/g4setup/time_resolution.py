"""The setup of the time-resolution experiment: a reference and a device under test between boards.

What surrounds the device in Geant4; reading it imports no Geant4."""

G4SETUP = {
    "name": "time_resolution",
    "geant4_model": "time_resolution",
    "total_events": 10000,
    "materials": {
        "SiO2": {"density": 2.2, "elements": {"Si": 1, "O": 2}},
    },
    "objects": {
        "Al": {"shape": "box", "size": [5000, 5000, 10], "material": "G4_Al", "colour": [1, 0.1, 0.8]},
        "pcb1": {"shape": "box", "size": [20000, 20000, 1500], "hole": 500, "material": "SiO2", "colour": [0, 0.5, 0.8]},
        "pcb2": {"shape": "box", "size": [20000, 20000, 1500], "hole": 500, "material": "SiO2", "colour": [0, 0.5, 0.8]},
    },
    "source": {"angle": 0},
    "along_beam": [
        "source",
        {"gap": 1990},
        "Al",
        {"gap": 0},
        {"slot": "ref"},
        "pcb1",
        {"gap": 500},
        {"slot": "dut"},
        "pcb2",
    ],
    "world": "G4_Galactic",
    "maxstep": 2,
    "g4_vis": False,
}
