from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.geant4


def test_binary_compound_takes_shares_of_atoms() -> None:
    from raser.core.deposit.geant4.detector_construction import GeneralDetectorConstruction

    device = SimpleNamespace(l_x=100, l_y=100, l_z=50)
    configuration = {"world": "G4_Galactic", "geant4_model": "device", "object": {}}
    construction = GeneralDetectorConstruction(device, configuration, "SiC", 2)
    silicon_carbide = construction.compound_materials["SiC"][0]
    atoms = silicon_carbide.GetVecNbOfAtomsPerVolume()
    silicon, carbon = atoms[0], atoms[1]

    # silicon carbide has as many carbon atoms as silicon atoms
    assert carbon / silicon == pytest.approx(1.0, rel=1e-6)
    # and about 70.0 % of its mass is silicon (28.086 / (28.086 + 12.011))
    assert silicon_carbide.GetFractionVector()[0] == pytest.approx(0.7005, abs=2e-4)
