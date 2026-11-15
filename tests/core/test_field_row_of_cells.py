from __future__ import annotations

import math
from types import SimpleNamespace

import numpy as np
import pytest


def _strips(cells: int) -> SimpleNamespace:
    """A slab 10 um deep with `cells` cells 4 um wide side by side: on top of
    each a strip from 1 to 3 um of its cell, below all of them one electrode.
    One strip is listed."""
    centimetre = 1e-4
    lines = [{"dir": "x", "pos": depth * centimetre, "ps": centimetre} for depth in (-1, 0, 10, 11)]
    lines += [{"dir": "y", "pos": across * centimetre, "ps": centimetre} for across in (0, 4 * cells)]
    contacts = [
        {"name": "top" if cells == 1 else f"top{number}", "material": "metal", "region": "slab",
         "xl": 0, "xh": 0, "yl": (4 * number + 1) * centimetre, "yh": (4 * number + 3) * centimetre,
         "bloat": 1e-10}
        for number in range(cells)
    ]  # fmt: skip
    contacts.append(
        {"name": "bot", "material": "metal", "region": "slab",
         "xl": 10 * centimetre, "xh": 10 * centimetre, "bloat": 1e-10}
    )  # fmt: skip
    regions = [
        {"material": "Silicon", "region": "slab"},
        {"material": "air", "region": "above", "xl": -centimetre, "xh": 0},
        {"material": "air", "region": "below", "xl": 10 * centimetre, "xh": 11 * centimetre},
    ]
    return SimpleNamespace(
        device_dict={
            "read_out_contact": [{"name": "top"}],
            "mesh": {"2D_mesh": {"mesh_line": lines, "region": regions, "contact": contacts}},
        },
        det_name="slab", dimension=2, device="slab", region="slab", file=None, p_x=4.0,
    )  # fmt: skip


def _nodes(contact: str | None = None) -> np.ndarray:
    """The places of the nodes of the slab, or of one of its electrodes, in um."""
    import devsim

    places = np.column_stack(
        [devsim.get_node_model_values(device="slab", region="slab", name=axis) for axis in "xy"]
    )
    if contact is not None:
        on = devsim.get_element_node_list(device="slab", region="slab", contact=contact)
        places = places[np.unique(on)]
    return np.round(places * 1e4, 6)


WEIGHTING = {"weightfield": True, "ac-weightfield": False}


def _clear() -> None:
    """devsim without its devices and meshes; its solver stays as loaded."""
    import devsim

    for device in devsim.get_device_list():
        devsim.delete_device(device=device)
    for mesh in devsim.get_mesh_list():
        devsim.delete_mesh(mesh=mesh)


@pytest.mark.devsim
def test_a_cell_laid_side_by_side_is_the_mesh_of_the_row_with_the_listed_electrode_in_the_middle() -> (
    None
):
    import devsim

    from raser.core.field.create_mesh import DevsimMesh

    try:
        DevsimMesh(_strips(3), WEIGHTING).create2DMesh()
        whole = {tuple(place) for place in _nodes()}
        _clear()

        DevsimMesh(_strips(1), WEIGHTING, cells_either_side=1).createRowOfCells()
        row = _nodes()
        contacts = set(devsim.get_contact_list(device="slab"))
        read_out, neighbours, back = _nodes("top"), _nodes("neighbour1"), _nodes("bot")
    finally:
        _clear()

    # the nodes two cells share are there once
    assert len(row) == len(whole)
    assert {tuple(place) for place in row} == whole
    assert contacts == {"top", "neighbour1", "bot"}
    assert sorted(read_out[:, 1]) == [5.0, 6.0, 7.0]
    assert sorted(neighbours[:, 1]) == [1.0, 2.0, 3.0, 9.0, 10.0, 11.0]
    assert sorted(back[:, 1]) == list(np.arange(0.0, 13.0))


@pytest.mark.devsim
def test_a_mesh_that_is_not_one_pitch_wide_is_not_laid_side_by_side() -> None:
    from raser.core.field.create_mesh import DevsimMesh

    device = _strips(1)
    device.p_x = 5.0
    try:
        with pytest.raises(ValueError, match="4 um wide, not one pitch of 5 um"):
            DevsimMesh(device, WEIGHTING, cells_either_side=1).createRowOfCells()
    finally:
        _clear()


@pytest.mark.parametrize(
    ("depth", "pitch", "tolerance"), [(305.0, 75.5, 5e-2), (50.0, 25.0, 1e-2), (300.0, 20.0, 1e-3)]
)
def test_the_cells_of_a_row_leave_the_tolerance_at_its_ends(depth: float, pitch: float, tolerance: float) -> None:
    from raser.core.field.solver_section import cells_to_fall_off

    def left(cells: int) -> float:
        # what reaches the end of the row, doubled by its reflection there
        return 2 * math.exp(-math.pi * cells * pitch / depth)

    cells = cells_to_fall_off(depth, pitch, tolerance)

    assert left(cells) <= tolerance < left(cells - 1)


@pytest.mark.devsim
def test_what_is_left_of_a_potential_is_looked_for_in_the_two_end_cells() -> None:
    import devsim

    from raser.core.field.create_mesh import DevsimMesh
    from raser.core.field.solver_section import left_at_the_ends

    try:
        DevsimMesh(_strips(1), WEIGHTING, cells_either_side=2).createRowOfCells()
        across = _nodes()[:, 1]  # five cells of 4 um
        potential = np.select([across < 4, across > 16, abs(across - 10) <= 2], [0.3, 0.2, 1.0], 0.7)
        devsim.node_solution(device="slab", region="slab", name="Potential")
        devsim.set_node_values(device="slab", region="slab", name="Potential", values=potential.tolist())

        assert left_at_the_ends("slab", "slab", 4e-4) == pytest.approx(0.3)
    finally:
        _clear()


def test_neighbours_are_coupled_as_far_as_they_hold_the_tolerance_of_the_capacitance() -> None:
    from raser.core.field.solver_section import neighbours_coupled

    # of 100 in all, the third pair of neighbours holds the tolerance and the fourth less
    tolerance = 0.02
    edge = 100 * tolerance
    to_others = {"bot": 25.0 - 1.5 * edge, "neighbour1": 55.0, "neighbour2": 20.0, "neighbour3": edge,
                 "neighbour4": 0.4 * edge, "neighbour5": 0.1 * edge}  # fmt: skip

    assert neighbours_coupled(to_others, tolerance) == 3
    # with a tolerance the fourth pair holds too, it is the fifth that does not
    assert neighbours_coupled(to_others, 0.4 * tolerance) == 4
    # a pair further away that holds more again is past the first that does not
    assert neighbours_coupled({**to_others, "neighbour5": 2 * edge, "bot": 25.0 - 3.4 * edge}, tolerance) == 3
