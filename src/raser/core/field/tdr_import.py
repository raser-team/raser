"""Create a DEVSIM device from materialized TDR data.

Derived from tdr-convert 0.1.7, commit
4151e42584bcf78c0d0c2693c3bd693747f634e4. Copyright 2024 DEVSIM LLC.
Licensed under the Apache License, Version 2.0. Modified for RASER in 2026.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import devsim
import numpy as np

from .tdr_reader import read_tdr


def _create_mesh(mesh_name: str, data: dict[str, Any]) -> None:
    devsim.create_gmsh_mesh(
        mesh=mesh_name,
        coordinates=data["coordinates"],
        physical_names=data["physical_names"],
        elements=data["elements"],
    )
    for region in data["regions"]:
        name = region["name"]
        if region["typename"] == "region":
            devsim.add_gmsh_region(
                mesh=mesh_name,
                region=name,
                gmsh_name=name,
                material=region["material"],
            )
        elif region["typename"] == "contact":
            devsim.add_gmsh_contact(
                mesh=mesh_name,
                name=name,
                gmsh_name=name,
                material=region["material"],
                region=region["bulk 0 name"],
            )
        elif region["typename"] == "interface":
            devsim.add_gmsh_interface(
                mesh=mesh_name,
                name=name,
                gmsh_name=name,
                region0=region["bulk 0 name"],
                region1=region["bulk 1 name"],
            )
        else:
            raise RuntimeError(f"Unsupported TDR region kind: {region['typename']}")
    devsim.finalize_mesh(mesh=mesh_name)


def _create_node_solution(
    *, device: str, region: str, name: str, values: np.ndarray
) -> None:
    devsim.node_solution(device=device, region=region, name=name)
    if np.unique(values).shape[0] == 1:
        devsim.set_node_value(
            device=device,
            region=region,
            name=name,
            value=values[0],
        )
    else:
        devsim.set_node_values(
            device=device,
            region=region,
            name=name,
            values=values,
        )


def _create_datasets(device_name: str, data: dict[str, Any]) -> None:
    for dataset in data["datasets"]:
        region_name = data["regions"][dataset["region"]]["name"]
        values = dataset["values"]
        if dataset["nrows"] == 1:
            _create_node_solution(
                device=device_name,
                region=region_name,
                name=dataset["name"],
                values=values[0, :],
            )
        else:
            for row_index in range(dataset["nrows"]):
                _create_node_solution(
                    device=device_name,
                    region=region_name,
                    name=f"{dataset['name']}_{row_index}",
                    values=values[row_index, :],
                )


def import_tdr(
    input_path: str | Path,
    output_path: str | Path,
    *,
    device_name: str = "device",
    mesh_name: str = "mesh",
    scale: float = 1.0,
    drop_interfaces_at_contact: bool = False,
) -> str:
    """Load a TDR file into DEVSIM and write the converted DEVSIM file."""
    data = read_tdr(
        str(input_path),
        scale=scale,
        load_datasets=True,
        drop_interfaces_at_contact=drop_interfaces_at_contact,
    )
    _create_mesh(mesh_name, data)
    devsim.create_device(mesh=mesh_name, device=device_name)
    _create_datasets(device_name, data)
    devsim.write_devices(file=str(output_path))
    return device_name
