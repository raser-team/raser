import json

import pytest

from raser.supports.paths import PACKAGE_ROOT
from raser.supports.paths import app_file_path
from raser.supports.paths import component_file_path


COMPONENT_ROOT = PACKAGE_ROOT / "components"
DETECTOR_CONFIG_KEYS = {
    "U_const",
    "area_factor",
    "avalanche_bond",
    "avalanche_model",
    "bias",
    "comment",
    "cross_talk",
    "current_savgol_poly",
    "current_savgol_window",
    "current_smoothing_window",
    "default_dimension",
    "det_model",
    "det_name",
    "doping",
    "e_gap",
    "e_r",
    "e_t",
    "field_shift_r",
    "field_shift_x",
    "field_shift_y",
    "irradiation",
    "l_x",
    "l_y",
    "l_z",
    "material",
    "mesh",
    "p_r",
    "p_x",
    "p_y",
    "parameter",
    "read_ele_num",
    "read_out_contact",
    "temperature",
    "vector_boundary_tolerance",
    "vector_delta_t",
    "vector_min_field_strength",
    "x_ele_num",
    "y_ele_num",
}


def _load_json(path):
    with open(path, encoding="utf-8") as file:
        return json.load(file)


def test_all_component_and_app_json_files_parse():
    roots = [COMPONENT_ROOT, PACKAGE_ROOT / "apps"]
    json_files = [
        path
        for root in roots
        for path in root.rglob("*.json")
    ]

    assert json_files
    for path in json_files:
        _load_json(path)


def test_detector_configs_expose_runtime_fields():
    detector_files = sorted((COMPONENT_ROOT / "detector").glob("*.json"))

    assert detector_files
    for path in detector_files:
        config = _load_json(path)
        assert set(config) <= DETECTOR_CONFIG_KEYS, path
        assert config["det_name"], path
        assert config["material"], path
        assert config["default_dimension"] in {1, 2, 3}, path
        assert "voltage" in config["bias"], path
        assert "electrode" in config["bias"], path
        assert config["mesh"], path


def test_source_configs_expose_particle_or_laser_fields():
    particle_required = {"name", "kind", "par_type", "par_energy", "par_in", "par_out"}
    for path in sorted((COMPONENT_ROOT / "source" / "beam").glob("*.json")):
        assert particle_required <= set(_load_json(path)), path
    for path in sorted((COMPONENT_ROOT / "source" / "decay").glob("*.json")):
        assert particle_required <= set(_load_json(path)), path

    laser_required = {
        "tech",
        "direction",
        "laser_model",
        "wavelength",
        "temporal_FWHM",
        "pulse_energy",
    }
    for path in sorted((COMPONENT_ROOT / "source" / "laser").glob("*.json")):
        assert laser_required <= set(_load_json(path)), path


def test_electronics_configs_expose_readout_thresholds():
    analog_required = {"ele_name", "noise_avg", "noise_rms", "threshold"}
    for path in sorted((COMPONENT_ROOT / "electronics" / "analog").glob("*.json")):
        assert analog_required <= set(_load_json(path)), path

    digital_required = {"threshold", "amplitude_threshold"}
    for path in sorted((COMPONENT_ROOT / "electronics" / "digital").glob("*.json")):
        assert digital_required <= set(_load_json(path)), path


def test_representative_components_are_discoverable_by_runtime_helpers():
    assert component_file_path("detector", "HPK-Si-PiN").exists()
    assert component_file_path("source/decay", "Am241").exists()
    assert component_file_path("source/beam", "proton").exists()
    assert component_file_path("source/laser", "SPA_top_Si").exists()
    assert component_file_path("electronics/analog", "Broad_Band_UCSC").exists()
    assert component_file_path("electronics/digital", "Alibava").exists()


def test_app_level_json_configs_are_discoverable():
    assert app_file_path("cce", "charge_collection.json").exists()
    assert app_file_path("timeres", "time_resolution.json").exists()
    assert app_file_path("bmos", "bmos.json").exists()
    assert app_file_path("telescope", "telescope.json").exists()
    telescope = _load_json(app_file_path("telescope", "telescope.json"))
    assert telescope["par_type"] == "e-"
    assert telescope["par_energy"] >= 1000


def test_planar_detector_estimates_capacitance_from_geometry():
    from raser.core.device.build_device import Detector

    detector = Detector("HPK-Si-PiN")

    assert detector.capacitance == pytest.approx(3.44, rel=0.01)


def test_3d_detector_requires_explicit_capacitance():
    from raser.core.device.build_device import Detector

    detector = Detector("3d_pixel")

    assert detector.capacitance is None
