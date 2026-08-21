"""Read Sentaurus TDR geometry and datasets.

Derived from tdr-convert 0.1.7, commit
4151e42584bcf78c0d0c2693c3bd693747f634e4. Copyright 2024 DEVSIM LLC.
Licensed under the Apache License, Version 2.0. Modified for RASER in 2026.
"""

from __future__ import annotations

from typing import Any

import h5py
import numpy as np


def _shape_name(dimension: int) -> str:
    names = {0: "points", 1: "edges", 2: "triangles", 3: "tetrahedra"}
    try:
        return names[dimension]
    except KeyError as error:
        raise RuntimeError(f"Unsupported element dimension: {dimension}") from error


def _process_elements(values: np.ndarray) -> dict[str, Any]:
    element_type = int(values[0])
    dimensions = {1: 1, 2: 2, 5: 3}
    try:
        dimension = dimensions[element_type]
    except KeyError as error:
        raise RuntimeError(f"Unsupported TDR element type: {element_type}") from error

    stride = dimension + 2
    if np.unique(values[0::stride]).shape[0] != 1:
        raise RuntimeError("Mixed TDR element types are not supported")

    elements = np.delete(values, np.s_[0::stride])
    coordinates = np.unique(elements)
    return {
        "dim": dimension,
        "coordinates": coordinates,
        _shape_name(dimension): np.reshape(elements, (-1, dimension + 1)),
    }


def _process_regions(geometry: h5py.Group) -> list[dict[str, Any]]:
    regions = []
    for index in range(int(geometry.attrs["number of regions"])):
        source = geometry[f"region_{index}"]
        if source.attrs["number of parts"] != 1:
            raise RuntimeError(f"Expected one part in TDR region {index}")

        region_type = int(source.attrs["type"])
        region = {
            "index": index,
            "name": source.attrs["name"].decode("ascii"),
            "elements": _process_elements(source["elements_0"][()]),
            "type": region_type,
        }
        if region_type == 0:
            region["typename"] = "region"
            region["material"] = source.attrs["material"].decode("ascii")
        elif region_type == 1:
            region["typename"] = "contact"
            region["material"] = "metal"
            region["bulk 0"] = int(source.attrs["bulk 0"])
        elif region_type == 2:
            region["typename"] = "interface"
            region["bulk 0"] = int(source.attrs["bulk 0"])
            region["bulk 1"] = int(source.attrs["bulk 1"])
        else:
            raise RuntimeError(f"Unsupported TDR region type: {region_type}")
        regions.append(region)
    return regions


def _intersection_elements(intersection: set[tuple[int, ...]]) -> np.ndarray:
    return np.array(sorted(intersection))


def _remove_interfaces_at_contact(regions: list[dict[str, Any]]) -> None:
    contact_nodes = set()
    for contact in (region for region in regions if region["type"] == 1):
        for surface in contact["surface_set"]:
            contact_nodes.update(surface)

    for interface in (region for region in regions if region["type"] == 2):
        surfaces = interface["surface_set"]
        remaining = {
            surface for surface in surfaces if not contact_nodes.intersection(surface)
        }
        if not remaining:
            raise RuntimeError(f"Interface {interface['name']} disappeared")
        if remaining != surfaces:
            interface["surface_set"] = remaining
            dimension = interface["elements"]["dim"]
            interface["elements"][_shape_name(dimension)] = _intersection_elements(
                remaining
            )


def _contact_is_in_region(region: dict[str, Any], contact: dict[str, Any]) -> bool:
    intersection = region["surface_set"].intersection(contact["surface_set"])
    return len(intersection) == len(contact["surface_set"])


def _split_contact(
    regions: list[dict[str, Any]], contact: dict[str, Any]
) -> list[dict[str, Any]]:
    contacts = []
    for region in regions:
        if region["type"] != 0:
            continue
        intersection = region["surface_set"].intersection(contact["surface_set"])
        if not intersection:
            continue
        dimension = contact["elements"]["dim"]
        contacts.append(
            {
                "name": f"{contact['name']}_{region['name']}",
                "type": 1,
                "typename": "contact",
                "material": "metal",
                "bulk 0": region["index"],
                "bulk 0 name": region["name"],
                "surface_set": intersection,
                "elements": {
                    "dim": dimension,
                    _shape_name(dimension): _intersection_elements(intersection),
                },
            }
        )
    return contacts


def _update_boundary_regions(regions: list[dict[str, Any]]) -> None:
    contacts_to_add = []
    for region in regions:
        if region["type"] == 1:
            bulk_index = region["bulk 0"]
            if _contact_is_in_region(regions[bulk_index], region):
                region["bulk 0 name"] = regions[bulk_index]["name"]
                continue

            matching_region = next(
                (
                    candidate
                    for candidate in regions
                    if candidate["type"] == 0
                    and _contact_is_in_region(candidate, region)
                ),
                None,
            )
            if matching_region is not None:
                region["bulk 0"] = matching_region["index"]
                region["bulk 0 name"] = matching_region["name"]
                continue

            split_contacts = _split_contact(regions, region)
            if not split_contacts:
                raise RuntimeError(f"Could not attach contact {region['name']}")
            contacts_to_add.append((region["index"], split_contacts))
        elif region["type"] == 2:
            region["bulk 0 name"] = regions[region["bulk 0"]]["name"]
            region["bulk 1 name"] = regions[region["bulk 1"]]["name"]

    for index, contacts in contacts_to_add:
        regions[index] = contacts[0]
        regions[index]["index"] = index
        for contact in contacts[1:]:
            contact["index"] = len(regions)
            regions.append(contact)


def _extract_volume_surface(region: dict[str, Any]) -> None:
    elements = region["elements"]
    dimension = elements["dim"]
    if dimension == 3:
        volume = elements["tetrahedra"]
    elif dimension == 2:
        volume = elements["triangles"]
    else:
        raise RuntimeError(f"Unsupported volume dimension: {dimension}")

    candidate_surfaces: list[tuple[int, ...]] = []
    for element in volume:
        nodes = sorted(int(node) for node in element)
        if dimension == 3:
            candidate_surfaces.extend(
                (
                    (nodes[0], nodes[1], nodes[2]),
                    (nodes[0], nodes[1], nodes[3]),
                    (nodes[0], nodes[2], nodes[3]),
                    (nodes[1], nodes[2], nodes[3]),
                )
            )
        else:
            candidate_surfaces.extend(
                (
                    (nodes[0], nodes[1]),
                    (nodes[0], nodes[2]),
                    (nodes[1], nodes[2]),
                )
            )

    surfaces: set[tuple[int, ...]] = set()
    duplicates: set[tuple[int, ...]] = set()
    for surface in candidate_surfaces:
        if surface in duplicates:
            continue
        if surface in surfaces:
            surfaces.remove(surface)
            duplicates.add(surface)
        else:
            surfaces.add(surface)
    region["surface_set"] = surfaces


def _extract_contact_surface(region: dict[str, Any]) -> None:
    elements = region["elements"]
    shapes = elements[_shape_name(elements["dim"])]
    region["surface_set"] = {
        tuple(sorted(int(node) for node in shape)) for shape in shapes
    }


def _find_interfaces(regions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    interfaces = []
    bulk_regions = [region for region in regions if region["typename"] == "region"]
    for first_index, first in enumerate(bulk_regions[:-1]):
        dimension = first["elements"]["dim"]
        for second in bulk_regions[first_index + 1 :]:
            intersection = first["surface_set"].intersection(second["surface_set"])
            if not intersection:
                continue
            interfaces.append(
                {
                    "name": f"{first['name']}_{second['name']}",
                    "type": 2,
                    "typename": "interface",
                    "bulk 0": first["index"],
                    "bulk 0 name": first["name"],
                    "bulk 1": second["index"],
                    "bulk 1 name": second["name"],
                    "surface_set": intersection,
                    "elements": {
                        "dim": dimension - 1,
                        _shape_name(dimension - 1): _intersection_elements(
                            intersection
                        ),
                    },
                }
            )
    return interfaces


def _encoded_elements(region: dict[str, Any]) -> list[int]:
    elements = region["elements"]
    physical_index = region["physical_index"]
    encoded: list[int] = []
    if "tetrahedra" in elements:
        for element in elements["tetrahedra"]:
            encoded.extend((3, physical_index, *(int(node) for node in element)))
    elif "triangles" in elements:
        for element in elements["triangles"]:
            encoded.extend((2, physical_index, *(int(node) for node in element)))
    elif "edges" in elements:
        for element in elements["edges"]:
            encoded.extend((1, physical_index, *(int(node) for node in element)))
    elif "points" in elements:
        for element in elements["points"]:
            encoded.extend((0, physical_index, int(element)))
    return encoded


def _write_devsim_metadata(regions: list[dict[str, Any]]) -> None:
    for region in regions:
        if region["type"] == 0:
            region["out_info"] = {
                "name": region["name"],
                "material": region["material"],
                "elements": _encoded_elements(region),
            }
        elif region["type"] == 1:
            region["out_info"] = {
                "name": region["name"],
                "region": region["bulk 0 name"],
                "material": region["material"],
                "elements": _encoded_elements(region),
            }
        else:
            region["out_info"] = {
                "name": region["name"],
                "region0": region["bulk 0 name"],
                "region1": region["bulk 1 name"],
                "elements": _encoded_elements(region),
            }


def _coordinates(vertex: h5py.Dataset, scale: float) -> np.ndarray:
    coordinate_count = len(vertex.dtype)
    if coordinate_count not in (2, 3):
        raise RuntimeError(f"Unsupported coordinate dimension: {coordinate_count}")
    fields = ("x", "y", "z")[:coordinate_count]
    selected = vertex[fields]
    coordinates: list[float] = []
    for point in selected:
        coordinates.extend(float(value) * scale for value in point)
        if coordinate_count == 2:
            coordinates.append(0.0)
    return np.array(coordinates)


def read_geometry(
    geometry: h5py.Group,
    *,
    scale: float = 1.0,
    drop_interfaces_at_contact: bool = False,
) -> dict[str, Any]:
    """Read one materialized TDR geometry from an open HDF5 group."""
    coordinates = _coordinates(geometry["vertex"], scale)
    regions = _process_regions(geometry)

    for region in regions:
        if region["type"] == 0:
            _extract_volume_surface(region)
        else:
            _extract_contact_surface(region)
    _update_boundary_regions(regions)

    if not any(region["type"] == 2 for region in regions):
        for interface in _find_interfaces(regions):
            interface["index"] = len(regions)
            regions.append(interface)
    if drop_interfaces_at_contact:
        _remove_interfaces_at_contact(regions)

    for physical_index, region in enumerate(regions):
        region["physical_index"] = physical_index
    _write_devsim_metadata(regions)

    elements = []
    for region in regions:
        elements.extend(region["out_info"]["elements"])
    return {
        "coordinates": coordinates,
        "physical_names": [region["name"] for region in regions],
        "elements": elements,
        "regions": regions,
        "dimension": int(geometry.attrs["dimension"]),
    }


def read_datasets(geometry: h5py.Group, data: dict[str, Any]) -> list[dict[str, Any]]:
    """Materialize scalar and vector node datasets for bulk regions."""
    datasets = []
    for dataset_name, source in geometry["state_0"].items():
        if not dataset_name.startswith("dataset"):
            continue
        region_index = int(source.attrs["region"])
        if data["regions"][region_index]["type"] != 0:
            continue

        values = source["values"][()]
        structure_type = int(source.attrs["structure type"])
        location_type = int(source.attrs["location type"])
        row_count = int(source.attrs.get("number of rows", 1))
        if location_type != 0 or structure_type not in (0, 1):
            continue

        node_count = len(data["regions"][region_index]["elements"]["coordinates"])
        if node_count != len(values) // row_count:
            raise RuntimeError(
                f"Dataset {dataset_name} has {len(values)} values for "
                f"{node_count} nodes and {row_count} rows"
            )
        datasets.append(
            {
                "name": source.attrs["name"].decode("ascii"),
                "region": region_index,
                "values": np.transpose(values.reshape(-1, row_count)),
                "dataset": dataset_name,
                "nrows": row_count,
            }
        )
    return datasets


def read_tdr(
    filename: str,
    *,
    scale: float = 1.0,
    load_datasets: bool = True,
    drop_interfaces_at_contact: bool = False,
) -> dict[str, Any]:
    """Read a TDR file without retaining an open HDF5 handle."""
    with h5py.File(filename, "r") as source:
        geometry = source["collection"]["geometry_0"]
        data = read_geometry(
            geometry,
            scale=scale,
            drop_interfaces_at_contact=drop_interfaces_at_contact,
        )
        data["datasets"] = read_datasets(geometry, data) if load_datasets else []
    return data
