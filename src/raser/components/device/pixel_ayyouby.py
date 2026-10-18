"""Deterministic tetrahedral mesh for the 3 x 3 Ayyoub DJ-LGAD pixel.

Coordinates in the Gmsh 2.2 file are cm, ordered (depth, pixel x, pixel y).
Every Cartesian cell uses the same conforming six-tetrahedron subdivision.
The full Cartesian node set is retained for exact nonuniform-grid field
interpolation. Contact faces cover only the nine metal windows and backside.
"""

from __future__ import annotations

import itertools
import json
import math
from pathlib import Path


CM_PER_UM = 1.0e-4


def contact_boxes_um(definition: dict) -> dict[str, tuple[float, ...]]:
    width = float(definition["electrode_width_um"])
    contacts = definition["read_out_contact"]
    nx, ny = int(definition["x_ele_num"]), int(definition["y_ele_num"])
    if len(contacts) != nx * ny:
        raise ValueError("Pixel contact count must equal x_count times y_count")
    if not 0 < width < min(definition["p_x"], definition["p_y"]):
        raise ValueError("Pixel metal width must be positive and below the pitch")
    return {
        contacts[j * nx + i]["name"]: (
            i * definition["p_x"],
            i * definition["p_x"] + width,
            j * definition["p_y"],
            j * definition["p_y"] + width,
        )
        for j in range(ny)
        for i in range(nx)
    }


def generate_mesh(
    destination: str | Path | None = None, *, definition: dict | None = None
) -> Path:
    """Write the model's physical volume/contact mesh, without running a solver."""
    raw = (
        json.loads(Path(__file__).with_suffix(".json").read_text())
        if definition is None
        else definition
    )
    axes = tuple(
        tuple(map(float, raw["mesh"]["gmsh_mesh"]["axes_um"][axis]))
        for axis in ("depth", "pixel_x", "pixel_y")
    )
    for axis, extent in zip(axes, (raw["l_z"], raw["l_x"], raw["l_y"])):
        if (
            len(axis) < 2
            or not all(math.isfinite(v) for v in axis)
            or axis[0] != 0
            or axis[-1] != extent
            or any(b <= a for a, b in zip(axis, axis[1:]))
        ):
            raise ValueError(
                "Mesh axes must be finite, strictly increasing and span the device"
            )
    contacts = contact_boxes_um(raw)
    for xmin, xmax, ymin, ymax in contacts.values():
        if any(v not in axes[1] for v in (xmin, xmax)) or any(
            v not in axes[2] for v in (ymin, ymax)
        ):
            raise ValueError("The mesh must contain every electrode edge")
    path = (
        Path(__file__).with_suffix(".msh") if destination is None else Path(destination)
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    nd, nx, ny = map(len, axes)

    def node(i: int, j: int, k: int) -> int:
        return (i * nx + j) * ny + k + 1

    triangles = []
    for j in range(nx - 1):
        for k in range(ny - 1):
            x = 0.5 * (axes[1][j] + axes[1][j + 1])
            y = 0.5 * (axes[2][k] + axes[2][k + 1])
            pad = next(
                (
                    index
                    for index, box in enumerate(contacts.values(), 1)
                    if box[0] < x < box[1] and box[2] < y < box[3]
                ),
                None,
            )
            for depth_index, tag in ((0, pad), (nd - 1, len(contacts) + 1)):
                if tag is None:
                    continue
                a, b = node(depth_index, j, k), node(depth_index, j + 1, k)
                c, d = node(depth_index, j + 1, k + 1), node(depth_index, j, k + 1)
                triangles.extend(((tag, a, b, c), (tag, a, c, d)))
    tetrahedra = 6 * (nd - 1) * (nx - 1) * (ny - 1)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write("$MeshFormat\n2.2 0 8\n$EndMeshFormat\n$PhysicalNames\n")
        stream.write(f"{len(contacts) + 2}\n")
        for tag, name in enumerate(contacts, 1):
            stream.write(f'2 {tag} "{name}"\n')
        stream.write(f'2 {len(contacts) + 1} "bot"\n3 100 "{raw["det_name"]}"\n')
        stream.write(f"$EndPhysicalNames\n$Nodes\n{nd * nx * ny}\n")
        for i, depth in enumerate(axes[0]):
            for j, x in enumerate(axes[1]):
                for k, y in enumerate(axes[2]):
                    stream.write(
                        f"{node(i, j, k)} {depth * CM_PER_UM:.16g} {x * CM_PER_UM:.16g} {y * CM_PER_UM:.16g}\n"
                    )
        stream.write(f"$EndNodes\n$Elements\n{tetrahedra + len(triangles)}\n")
        element = 0
        for tag, a, b, c in triangles:
            element += 1
            stream.write(f"{element} 2 2 {tag} {tag} {a} {b} {c}\n")
        for i in range(nd - 1):
            for j in range(nx - 1):
                for k in range(ny - 1):
                    for permutation in itertools.permutations(range(3)):
                        position = [i, j, k]
                        vertices = [node(*position)]
                        for axis in permutation:
                            position[axis] += 1
                            vertices.append(node(*position))
                        inversions = sum(
                            permutation[a] > permutation[b]
                            for a in range(3)
                            for b in range(a + 1, 3)
                        )
                        if inversions % 2:
                            vertices[1], vertices[2] = vertices[2], vertices[1]
                        element += 1
                        stream.write(
                            f"{element} 4 2 100 100 {' '.join(map(str, vertices))}\n"
                        )
        stream.write("$EndElements\n")
    return path
