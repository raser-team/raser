"""The readout board of the PCB, imported from pcb_readout.gdml, which
patch_pcb_gdml_material.py writes from pcb_readout_raw.gdml.

What surrounds the device in Geant4; reading it imports no Geant4."""

G4SETUP = {
    "geant4_model": "gdml_import",
    "total_events": 1,
    "object": {},
    "world": "G4_Galactic",
    "world_half_size_um": 2000000,
    "par_type": "proton",
    "par_energy": 3000,
    "maxstep": 2,
    "g4_vis": False,
    "source": {"at": [0, 0, -60000], "towards": [0, 0, 10000], "angle": 0},
    "par_randx": 300,
    "par_randy": 300,
    "gdml": {
        "file": "pcb_readout.gdml",
        "top_volume": "World_Wrapper",
        "validate": False,
        "auto_center": False,
        "position_um": [0, 0, 0],
        "rotation_xyz": [0, 0, 0],
        "placement_name": "PCB_Readout",
    },
}
