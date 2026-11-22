from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.geant4


def _construction(configuration, column):
    from raser.core.deposit.along_beam import parse_along_beam
    from raser.core.deposit.geant4.detector_construction import GeneralDetectorConstruction

    device = SimpleNamespace(l_x=100, l_y=100, l_z=50, material="SiC")
    devices = {"Device": device}
    configuration = {
        "world": "G4_Galactic",
        "geant4_model": "device",
        "along_beam": ["source", {"gap": 100}, *column, {"slot": "Device"}],
        **configuration,
    }
    return GeneralDetectorConstruction(
        devices, parse_along_beam(configuration, devices), configuration, 2
    )


def test_silicon_carbide_has_as_many_carbon_atoms_as_silicon_atoms() -> None:
    construction = _construction({"materials": {}, "objects": {}}, [])
    silicon_carbide = construction.materials["SiC"]
    atoms = silicon_carbide.GetVecNbOfAtomsPerVolume()

    assert atoms[1] / atoms[0] == pytest.approx(1.0, rel=1e-6)
    # and about 70.0 % of its mass is silicon (28.086 / (28.086 + 12.011))
    assert silicon_carbide.GetFractionVector()[0] == pytest.approx(0.7005, abs=2e-4)


def test_shares_of_atoms_become_shares_of_mass_by_the_atomic_mass() -> None:
    construction = _construction(
        {
            "materials": {"SiO2": {"density": 2.2, "elements": {"Si": 1, "O": 2}}},
            "objects": {
                "pcb": {
                    "shape": "box",
                    "size": [10, 10, 10],
                    "hole": 2,
                    "material": "SiO2",
                }
            },
        },
        ["pcb"],
    )
    silica = construction.materials["SiO2"]

    # 28.086 / (28.086 + 2 * 15.999) = 0.4674 of the mass is silicon
    mass = silica.GetFractionVector()
    assert mass[0] == pytest.approx(0.4674, abs=1e-3)
    assert mass[1] == pytest.approx(0.5326, abs=1e-3)
    atoms = silica.GetVecNbOfAtomsPerVolume()
    assert atoms[1] / atoms[0] == pytest.approx(2.0, rel=1e-6)
    assert construction.logical["pcb"].GetMaterial().GetName() == "SiO2"


def test_a_material_with_three_elements_takes_all_of_them() -> None:
    construction = _construction(
        {"materials": {"FR4": {"density": 1.85, "elements": {"Si": 1, "O": 2, "H": 4}}}},
        [],
    )
    material = construction.materials["FR4"]
    fractions = material.GetFractionVector()
    mass = [fractions[i] for i in range(material.GetNumberOfElements())]

    assert len(mass) == 3
    assert sum(mass) == pytest.approx(1.0, abs=1e-9)
    assert mass[2] == pytest.approx(4 * 1.008 / (28.086 + 2 * 15.999 + 4 * 1.008), abs=1e-3)


@pytest.mark.parametrize(
    ("materials", "message"),
    [
        ({"G4_Al": {"density": 1, "elements": {"Si": 1}}}, "conflicts with a NIST material name"),
        ({"X": {"density": 1, "elements": {"Xx": 1}}}, "unknown Geant4 element 'Xx'"),
    ],
)
def test_a_material_geant4_cannot_build_is_refused(materials, message) -> None:
    with pytest.raises(ValueError, match=message):
        _construction({"materials": materials, "objects": {}}, [])


def test_a_tube_has_its_length_along_z_and_a_box_its_hole_through_all_of_it() -> None:
    construction = _construction(
        {
            "objects": {
                "pipe": {
                    "shape": "tube",
                    "inner_radius": 100,
                    "outer_radius": 200,
                    "length": 1000,
                    "material": "G4_Al",
                },
                "plate": {"shape": "box", "size": [1000, 1000, 40], "hole": 100, "material": "G4_Al"},
            }
        },
        ["pipe", "plate"],
    )
    from raser.core.deposit.geant4.g4ppyy_runtime import g4b

    pipe = construction.solid["pipe"]
    assert pipe.GetZHalfLength() == pytest.approx(500 * g4b.um, abs=0)
    assert pipe.GetOuterRadius() == pytest.approx(200 * g4b.um, abs=0)
    assert pipe.GetInnerRadius() == pytest.approx(100 * g4b.um, abs=0)
    # the plate follows the pipe: its centre is a length of the pipe plus half its thickness
    assert construction.physical["plate"].GetTranslation().z() == pytest.approx(
        (100 + 1000 + 20) * g4b.um, abs=1e-6
    )
    # the hole goes through the whole thickness: the middle of the plate is empty down to both faces (40 um thick)
    plate = construction.solid["plate"]
    for z in (-19, 0, 19):
        assert plate.Inside(g4b.G4ThreeVector(0, 0, z * g4b.um)) == g4b.kOutside
    assert plate.Inside(g4b.G4ThreeVector(300 * g4b.um, 0, 0)) == g4b.kInside
