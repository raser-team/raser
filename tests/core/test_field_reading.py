from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from raser.core.device.build_device import Detector
from raser.core.device.build_device import device_file
from raser.core.field.reading import Reading
from raser.core.field.reading import changed


def _content() -> dict:
    return json.loads(device_file("HPK-Si-PiN").read_text(encoding="utf-8"))


def _solve(my_d) -> None:
    """Reads a device the ways the field solve does."""
    my_d.dimension
    my_d.is_plugin()
    my_d.definition_path
    json_of_device = my_d.device_dict
    json_of_device["doping"]["Donors"]
    json_of_device["bias"]["electrode"]
    json_of_device["mesh"]["1D_mesh"]["mesh_line"]
    "irradiation" in json_of_device
    json_of_device.get("hemt_physics", {}).get("transport_model")


def test_a_reading_notes_what_is_read_and_nothing_else() -> None:
    device = Reading(Detector("HPK-Si-PiN", _content()))

    _solve(device)

    assert device.read["attributes"] == {"dimension": 1, "det_model": "planar"}
    keys = device.read["keys"]
    assert sorted(keys) == [
        "bias.electrode", "doping.Donors", "hemt_physics", "irradiation", "mesh.1D_mesh",
    ]
    assert keys["bias.electrode"] == "top"
    assert keys["irradiation"] is None
    assert keys["mesh.1D_mesh"].startswith("sha256:")


def test_a_field_is_out_of_date_only_for_what_its_solve_read() -> None:
    device = Reading(Detector("HPK-Si-PiN", _content()))
    _solve(device)
    read = json.loads(json.dumps(device.read))

    def now(change) -> list[str]:
        content = _content()
        change(content)
        return changed(read, Detector("HPK-Si-PiN", content))

    assert now(lambda content: None) == []
    assert now(lambda content: content["bias"].update(voltage=-321.0)) == []
    assert now(lambda content: content.update(capacitance_pF=9.9)) == []
    assert now(lambda content: content["doping"].update(Acceptors="1e13")) == []
    assert now(lambda content: content["doping"].update(Donors="1e18")) == ["doping.Donors"]
    assert now(lambda content: content["mesh"]["1D_mesh"]["mesh_line"].pop()) == ["mesh.1D_mesh"]
    assert now(lambda content: content.update(irradiation={"irradiation_flux": 1e15,
                                                           "irradiation_model": "Perugia"})) == ["irradiation"]
    assert now(lambda content: content.update(field_dimension=2)) == ["dimension"]


def test_what_the_solve_writes_into_the_json_stays_out_of_the_device() -> None:
    content = _content()
    before = copy.deepcopy(content)
    json_of_device = Reading(Detector("HPK-Si-PiN", content)).device_dict

    json_of_device["doping"]["Acceptors"] = "0"
    json_of_device.update({"doping": json_of_device["doping"]})

    assert json_of_device["doping"]["Acceptors"] == "0"
    assert content == before


def test_a_file_the_device_names_is_noted_by_its_content(tmp_path: Path) -> None:
    (tmp_path / "device.json").write_text(json.dumps(_content()), encoding="utf-8")
    (tmp_path / "strip.msh").write_text("mesh", encoding="utf-8")
    device = Reading(Detector(tmp_path))

    assert device.file("strip.msh") == (tmp_path / "strip.msh").resolve()
    read = json.loads(json.dumps(device.read))
    assert changed(read, Detector(tmp_path)) == []

    (tmp_path / "strip.msh").write_text("another mesh", encoding="utf-8")
    assert changed(read, Detector(tmp_path)) == ["strip.msh"]
    (tmp_path / "strip.msh").unlink()
    assert changed(read, Detector(tmp_path)) == ["strip.msh"]


SOLVE = ("solver_section", "create_mesh", "create_parameter", "initial", "loop_section",
         "model_create", "physics_drift_diffusion", "physics_irradiation",
         "physics_avalanche", "hemt_solver_2d_transport_v1")


@pytest.mark.parametrize("module", SOLVE)
def test_the_solve_takes_its_device_only_through_the_reading(module: str) -> None:
    import raser.core.field

    source = (Path(raser.core.field.__file__).parent / f"{module}.py").read_text(encoding="utf-8")
    source = source.replace("MyDetector = Reading(Detector(simname))", "")

    for way_around in ("Detector(", "device_file(", "load_definition(", "resolve_device(",
                       "definition_path", "json.load("):
        assert way_around not in source
