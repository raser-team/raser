"""The device alone in vacuum, the source 17 mm in front of its front face.

What surrounds the device in Geant4; reading it imports no Geant4."""

G4SETUP = {
    "name": "device_alone",
    "description": "The device alone in vacuum",
    "geant4_model": "device",
    "object": {},
    "source": {"angle": 0},
    "along_beam": ["source", {"gap": 17000}, {"slot": "Device"}],
    "world": "G4_Galactic",
    "maxstep": 2,
    "g4_vis": False,
}
