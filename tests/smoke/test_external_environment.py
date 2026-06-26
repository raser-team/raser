from pathlib import Path
import subprocess

import pytest


@pytest.mark.ngspice
def test_ngspice_executable_is_available():
    result = subprocess.run(
        ["ngspice", "-v"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "ngspice" in result.stdout.lower()


@pytest.mark.devsim
def test_tcad_devsim_asset_contains_semiconductor_models():
    devsim_file = Path("output/field/CMOS_strip_tcad/210.devsim")
    if not devsim_file.exists():
        pytest.skip(f"missing TCAD devsim smoke asset: {devsim_file}")

    import devsim

    devsim.load_devices(file=str(devsim_file))
    try:
        device = devsim.get_device_list()[-1]
        models = set(devsim.get_node_model_list(device=device, region="Silicon_1"))

        assert "DopingConcentration" in models
        assert "SpaceCharge" in models
        assert "eDensity" in models
        assert "hDensity" in models
    finally:
        devsim.reset_devsim()


@pytest.mark.geant4
def test_geant4_nist_materials_are_available():
    import g4ppyy as g4b

    nist = g4b.G4NistManager.Instance()

    assert nist.FindOrBuildMaterial("G4_Si")
