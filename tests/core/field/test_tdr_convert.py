from __future__ import annotations

from pathlib import Path

import h5py
import numpy as np
import pytest

from raser.core.field import tdr_import
from raser.core.field.tdr_reader import read_tdr


def _write_tdr(path: Path) -> None:
    with h5py.File(path, "w") as target:
        collection = target.create_group("collection")
        geometry = collection.create_group("geometry_0")
        geometry.attrs["dimension"] = 2
        geometry.attrs["number of regions"] = 1
        geometry.create_dataset(
            "vertex",
            data=np.array(
                [(0.0, 0.0), (10.0, 0.0), (0.0, 20.0)],
                dtype=[("x", "f8"), ("y", "f8")],
            ),
        )

        region = geometry.create_group("region_0")
        region.attrs["name"] = np.bytes_("bulk")
        region.attrs["material"] = np.bytes_("Silicon")
        region.attrs["type"] = 0
        region.attrs["number of parts"] = 1
        region.create_dataset("elements_0", data=np.array([2, 0, 1, 2]))

        state = geometry.create_group("state_0")
        dataset = state.create_group("dataset_0")
        dataset.attrs["name"] = np.bytes_("ElectrostaticPotential")
        dataset.attrs["region"] = 0
        dataset.attrs["structure type"] = 0
        dataset.attrs["location type"] = 0
        dataset.attrs["number of values"] = 3
        dataset.attrs["number of rows"] = 1
        dataset.create_dataset("values", data=np.array([1.0, 2.0, 3.0]))


def test_tdr_reader_materializes_scaled_geometry_and_dataset(tmp_path: Path) -> None:
    source = tmp_path / "sensor.tdr"
    _write_tdr(source)

    data = read_tdr(str(source), scale=1.0e-4)

    assert data["dimension"] == 2
    assert data["physical_names"] == ["bulk"]
    assert data["coordinates"] == pytest.approx(
        [0.0, 0.0, 0.0, 1.0e-3, 0.0, 0.0, 0.0, 2.0e-3, 0.0]
    )
    assert data["elements"] == [2, 0, 0, 1, 2]
    assert data["regions"][0]["material"] == "Silicon"
    assert data["datasets"][0]["name"] == "ElectrostaticPotential"
    assert data["datasets"][0]["values"][0] == pytest.approx([1.0, 2.0, 3.0])


def test_tdr_import_creates_devsim_device_and_writes_conversion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "sensor.tdr"
    output = tmp_path / "converted.devsim"
    _write_tdr(source)
    calls = []

    for name in (
        "create_gmsh_mesh",
        "add_gmsh_region",
        "finalize_mesh",
        "create_device",
        "node_solution",
        "set_node_value",
        "set_node_values",
        "write_devices",
    ):
        monkeypatch.setattr(
            tdr_import.devsim,
            name,
            lambda _name=name, **kwargs: calls.append((_name, kwargs)),
        )

    device = tdr_import.import_tdr(source, output)

    assert device == "device"
    assert [name for name, _ in calls] == [
        "create_gmsh_mesh",
        "add_gmsh_region",
        "finalize_mesh",
        "create_device",
        "node_solution",
        "set_node_values",
        "write_devices",
    ]
    assert calls[0][1]["physical_names"] == ["bulk"]
    assert calls[3][1] == {"mesh": "mesh", "device": "device"}
    assert calls[4][1]["name"] == "ElectrostaticPotential"
    assert calls[-1][1] == {"file": str(output)}
