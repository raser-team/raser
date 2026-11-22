"""Am-241 alphas on the MIM diamond pad, 0.2 um of gold on both faces, in vacuum.

What surrounds the device in Geant4; reading it imports no Geant4."""

G4SETUP = {
    "name": "mim_diamond_gold",
    "description": "Alphas on the MIM diamond pad with 0.2 um of gold on both faces, in vacuum",
    "geant4_model": "device",
    "world": "G4_Galactic",
    "object": {
        "elemental": {
            "FrontAu": {
                "name": "FrontAu", "material": "G4_Au", "side_x": 4500.0, "side_y": 4500.0, "side_z": 0.2,
                "colour": [1.0, 0.8, 0.0], "position_x": 0.0, "position_y": 0.0, "position_z": 500.1,
            },
            "BackAu": {
                "name": "BackAu", "material": "G4_Au", "side_x": 4500.0, "side_y": 4500.0, "side_z": 0.2,
                "colour": [1.0, 0.8, 0.0], "position_x": 0.0, "position_y": 0.0, "position_z": -0.1,
            },
        }
    },
    "source": {"at": [0, 0, 500.5], "towards": [0, 0, 474.2281], "angle": 0},
    "maxstep": 2,
    "g4_vis": False,
}
