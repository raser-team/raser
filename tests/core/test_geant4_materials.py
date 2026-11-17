from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.geant4


def test_binary_compound_takes_shares_of_atoms() -> None:
    from raser.core.deposit.geant4.detector_construction import GeneralDetectorConstruction

    device = SimpleNamespace(l_x=100, l_y=100, l_z=50)
    silica = {
        "name": "silica", "material_1": "Si", "material_2": "O", "compound_name": "SiO2",
        "density": 2.2, "natoms_1": 33.4, "natoms_2": 66.6, "side_x": 10, "side_y": 10,
        "side_z": 10, "colour": [0, 0, 1], "position_x": 0, "position_y": 0,
        "position_z": -100, "tub": {},
    }
    configuration = {
        "world": "G4_Galactic", "geant4_model": "device",
        "object": {"binary_compounds": {"silica": silica}},
    }
    construction = GeneralDetectorConstruction(device, configuration, "SiC", 2)
    silicon_carbide = construction.compound_materials["SiC"][0]
    atoms = silicon_carbide.GetVecNbOfAtomsPerVolume()
    silicon, carbon = atoms[0], atoms[1]

    # silicon carbide has as many carbon atoms as silicon atoms
    assert carbon / silicon == pytest.approx(1.0, rel=1e-6)
    # and about 70.0 % of its mass is silicon (28.086 / (28.086 + 12.011))
    assert silicon_carbide.GetFractionVector()[0] == pytest.approx(0.7005, abs=2e-4)

    # silica as the setups give it: 33.4 silicon atoms to 66.6 oxygen atoms
    atoms = construction.compound_materials["SiO2"][0].GetVecNbOfAtomsPerVolume()
    assert atoms[1] / atoms[0] == pytest.approx(66.6 / 33.4, rel=1e-6)
