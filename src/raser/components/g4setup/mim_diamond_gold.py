"""Am-241 alphas on the MIM diamond pad, 0.2 um of gold on both faces, in vacuum.

What surrounds the device in Geant4; reading it imports no Geant4."""

G4SETUP = {
    "name": "mim_diamond_gold",
    "description": "Alphas on the MIM diamond pad with 0.2 um of gold on both faces, in vacuum",
    "geant4_model": "device",
    "world": "G4_Galactic",
    "materials": {},
    "objects": {
        "FrontAu": {"shape": "box", "size": [4500.0, 4500.0, 0.2], "material": "G4_Au", "colour": [1.0, 0.8, 0.0]},
        "BackAu": {"shape": "box", "size": [4500.0, 4500.0, 0.2], "material": "G4_Au", "colour": [1.0, 0.8, 0.0]},
    },
    "source": {"angle": 0},
    # the alphas enter through the face z = l_z of the device, its top electrode
    "along_beam": ["source", {"gap": 0.3}, "FrontAu", {"slot": "Device", "facing": "downstream"}, "BackAu"],
    "maxstep": 2,
    "g4_vis": False,
}
