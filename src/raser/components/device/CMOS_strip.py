#!/usr/bin/env python3
# -*- encoding: utf-8 -*-
"""Generate the structured triangular Gmsh mesh for CMOS_strip."""

from __future__ import annotations

import math
from pathlib import Path

import gmsh

from raser.supports.output import create_path


CM = 1.0e-4
TRIANGLE_ARRANGEMENT = "Right"

X_LINES_UM = (0.0, 0.2, 0.4, 1.2, 1.6, 10.0, 140.0, 147.0, 149.0, 150.0)
Y_LINES_UM = (0.0, 1.0, 3.0, 28.75, 30.25, 45.25, 46.75, 72.5, 74.5, 75.5)

CMOS_STRIP_BLOCKS_UM = (
    (0.0, 0.4, 0.0, 1.0),
    (0.4, 1.6, 0.0, 3.0),
    (0.0, 0.4, 30.25, 45.25),
    (0.4, 1.2, 28.75, 46.75),
    (0.4, 1.6, 3.0, 28.75),
    (1.2, 1.6, 28.75, 46.75),
    (0.4, 1.6, 46.75, 72.5),
    (0.0, 0.4, 74.5, 75.5),
    (0.4, 1.6, 72.5, 75.5),
    (1.6, 10.0, 0.0, 75.5),
    (10.0, 140.0, 0.0, 75.5),
    (140.0, 147.0, 0.0, 75.5),
    (147.0, 149.0, 0.0, 75.5),
    (149.0, 150.0, 0.0, 75.5),
)


def inside_cmos_strip(point: tuple[float, float]) -> bool:
    x, y = point
    return any(
        x_low <= x <= x_high and y_low <= y <= y_high
        for x_low, x_high, y_low, y_high in CMOS_STRIP_BLOCKS_UM
    )


def x_spacing_um(x_low: float, x_high: float) -> float:
    midpoint = 0.5 * (x_low + x_high)
    if midpoint < 1.6:
        return 0.05
    if midpoint < 10.0:
        return 0.35
    if midpoint < 140.0:
        return 1.0
    if midpoint < 147.0:
        return 0.35
    return 0.15


def y_spacing_um(y_low: float, y_high: float) -> float:
    midpoint = 0.5 * (y_low + y_high)
    if midpoint < 3.0 or midpoint > 72.5:
        return 0.10
    if 28.75 < midpoint < 46.75:
        return 0.20
    return 0.75


def interval_subdivisions(lines_um, spacing_function):
    return tuple(
        max(1, math.ceil((high - low) / spacing_function(low, high)))
        for low, high in zip(lines_um, lines_um[1:])
    )


def _add_oriented_line(geo, lines, points, start, end):
    key = tuple(sorted((start, end)))
    if key not in lines:
        lines[key] = geo.addLine(points[key[0]], points[key[1]])
    line = lines[key]
    return line if key[0] == start else -line


def generate_mesh(destination: str | Path | None = None) -> Path:
    """Write a Gmsh 2.2 mesh and return its path."""
    mesh_path = Path(__file__).with_suffix(".msh") if destination is None else Path(destination)
    mesh_path = create_path(mesh_path.parent) / mesh_path.name

    gmsh.initialize()
    try:
        gmsh.model.add("CMOS_strip")
        geo = gmsh.model.geo
        mesh = geo.mesh
        points = {
            (ix, iy): geo.addPoint(x_um * CM, y_um * CM, 0.0)
            for ix, x_um in enumerate(X_LINES_UM)
            for iy, y_um in enumerate(Y_LINES_UM)
        }
        x_subdivisions = interval_subdivisions(X_LINES_UM, x_spacing_um)
        y_subdivisions = interval_subdivisions(Y_LINES_UM, y_spacing_um)
        lines = {}
        surfaces = []
        top_contact_lines = []
        bottom_contact_lines = []

        for ix, (x_low, x_high) in enumerate(zip(X_LINES_UM, X_LINES_UM[1:])):
            for iy, (y_low, y_high) in enumerate(zip(Y_LINES_UM, Y_LINES_UM[1:])):
                center = (0.5 * (x_low + x_high), 0.5 * (y_low + y_high))
                if not inside_cmos_strip(center):
                    continue
                bottom = _add_oriented_line(
                    geo, lines, points, (ix, iy), (ix + 1, iy)
                )
                right = _add_oriented_line(
                    geo, lines, points, (ix + 1, iy), (ix + 1, iy + 1)
                )
                top = _add_oriented_line(
                    geo, lines, points, (ix + 1, iy + 1), (ix, iy + 1)
                )
                left = _add_oriented_line(
                    geo, lines, points, (ix, iy + 1), (ix, iy)
                )
                loop = geo.addCurveLoop([bottom, right, top, left])
                surfaces.append(geo.addPlaneSurface([loop]))
                if ix == 0 and 30.25 <= y_low and y_high <= 45.25:
                    top_contact_lines.append(abs(left))
                if ix == len(X_LINES_UM) - 2:
                    bottom_contact_lines.append(abs(right))

        for (start, end), line in lines.items():
            if start[1] == end[1]:
                count = x_subdivisions[min(start[0], end[0])] + 1
            else:
                count = y_subdivisions[min(start[1], end[1])] + 1
            mesh.setTransfiniteCurve(line, count)
        for surface in surfaces:
            mesh.setTransfiniteSurface(surface, TRIANGLE_ARRANGEMENT)

        geo.synchronize()
        gmsh.model.addPhysicalGroup(1, top_contact_lines, name="top")
        gmsh.model.addPhysicalGroup(1, bottom_contact_lines, name="bot")
        gmsh.model.addPhysicalGroup(2, surfaces, name="CMOS_strip")
        gmsh.option.setNumber("Geometry.MatchMeshTolerance", 1.0e-12)
        gmsh.model.mesh.generate(2)
        gmsh.option.setNumber("Mesh.MshFileVersion", 2.2)
        gmsh.write(str(mesh_path))
    finally:
        gmsh.finalize()
    return mesh_path


def main():
    generate_mesh()


if __name__ == "__main__":
    main()
