"""In air, a brass collimator 5 mm thick with a hole 1 mm across between the Sr-90 source and the device.

What surrounds the device in Geant4; reading it imports no Geant4."""

G4SETUP = {
    "name": "Sr90_collimator",
    "description": "In air, a brass block 5 mm thick with a hole 1 mm across between the Sr-90 source (17 mm in front of the device) and the device: the block starts 0.5 mm behind the source and ends 11.5 mm in front of the device",
    "geant4_model": "collimator",
    "object": {
        "elemental": {
            "collimator": {
                "name": "collimator",
                "material": "G4_BRASS",
                "side_x": 10000,
                "side_y": 10000,
                "side_z": 5000,
                "colour": [0.8, 0.6, 0.2],
                "tub": {"tub_radius": 500, "tub_depth": 2600},
            }
        }
    },
    "source": {"angle": 0},
    "along_beam": [
        "source",
        {"gap": 500},
        "collimator",
        {"gap": 11500},
        {"slot": "Device"},
    ],
    "world": "G4_AIR",
    "maxstep": 2,
    "g4_vis": False,
}
