"""The setup of the time-resolution experiment: a reference and a device under test between boards.

What surrounds the device in Geant4; reading it imports no Geant4."""

G4SETUP = {
    "name": "time_resolution",
    "geant4_model": "time_resolution",
    "total_events": 10000,
    "object": {
        "elemental": {
            "Al": {
                "name": "Al",
                "material": "G4_Al",
                "side_x": 5000,
                "side_y": 5000,
                "side_z": 10,
                "colour": [1, 0.1, 0.8],
            },
        },
        "binary_compounds": {
            "pcb1": {
                "name": "pcb1",
                "material_1": "Si",
                "material_2": "O",
                "compound_name": "SiO2",
                "density": 2.2,
                "natoms_1": 33.4,
                "natoms_2": 66.6,
                "side_x": 20000,
                "side_y": 20000,
                "side_z": 1500,
                "colour": [0, 0.5, 0.8],
                "tub": {"tub_radius": 500, "tub_depth": 1500},
            },
            "pcb2": {
                "name": "pcb2",
                "material_1": "Si",
                "material_2": "O",
                "compound_name": "SiO2",
                "density": 2.2,
                "natoms_1": 33.4,
                "natoms_2": 66.6,
                "side_x": 20000,
                "side_y": 20000,
                "side_z": 1500,
                "colour": [0, 0.5, 0.8],
                "tub": {"tub_radius": 500, "tub_depth": 1500},
            },
        },
    },
    "source": {"angle": 0},
    "along_beam": [
        "source",
        {"gap": 1995},
        "Al",
        {"gap": 4978.5},
        {"slot": "ref"},
        "pcb1",
        {"gap": 8183.5},
        {"slot": "dut"},
        "pcb2",
    ],
    "world": "G4_Galactic",
    "maxstep": 2,
    "g4_vis": False,
}
