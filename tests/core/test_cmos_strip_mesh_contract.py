from __future__ import annotations

from pathlib import Path

import pytest


from raser.core.field.create_mesh import _resolve_mesh_file


pytest.importorskip("gmsh")
generate_mesh = pytest.importorskip("raser.components.device.CMOS_strip").generate_mesh


def _mesh_elements(path: Path):
    lines = path.read_text(encoding="utf-8").splitlines()
    nodes_start = lines.index("$Nodes")
    node_count = int(lines[nodes_start + 1])
    nodes = {}
    for line in lines[nodes_start + 2 : nodes_start + 2 + node_count]:
        tag, x, y, z = line.split()
        nodes[int(tag)] = (float(x), float(y), float(z))
    elements_start = lines.index("$Elements")
    element_count = int(lines[elements_start + 1])
    elements = []
    for line in lines[elements_start + 2 : elements_start + 2 + element_count]:
        fields = [int(field) for field in line.split()]
        element_type = fields[1]
        tag_count = fields[2]
        elements.append((element_type, fields[3 + tag_count :]))
    return nodes, elements


def test_cmos_strip_mesh_uses_one_triangular_orientation(tmp_path: Path) -> None:
    path = generate_mesh(tmp_path / "CMOS_strip.msh")
    nodes, elements = _mesh_elements(path)

    assert {element_type for element_type, _ in elements} == {1, 2}
    orientations = set()
    triangle_count = 0
    for element_type, node_tags in elements:
        if element_type != 2:
            continue
        triangle_count += 1
        points = [nodes[node_tag] for node_tag in node_tags]
        axis_aligned = 0
        for first, second in ((0, 1), (1, 2), (2, 0)):
            dx = points[second][0] - points[first][0]
            dy = points[second][1] - points[first][1]
            if dx == pytest.approx(0.0) or dy == pytest.approx(0.0):
                axis_aligned += 1
            else:
                orientations.add(dx * dy > 0.0)
        assert axis_aligned == 2
    assert triangle_count > 0
    assert len(orientations) == 1


def test_device_mesh_path_is_relative_to_its_definition(tmp_path: Path) -> None:
    definition_path = tmp_path / "device.json"
    definition_path.write_text("{}", encoding="utf-8")
    mesh_path = tmp_path / "CMOS_strip.msh"
    mesh_path.write_text("mesh", encoding="utf-8")

    assert _resolve_mesh_file("CMOS_strip.msh", definition_path) == mesh_path
