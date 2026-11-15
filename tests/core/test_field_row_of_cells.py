from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest


def _strips(cells: int) -> SimpleNamespace:
    """A slab 10 um deep with `cells` cells 4 um wide side by side: on top of
    each a strip from 1 to 3 um of its cell, below all of them one electrode.
    One strip is listed, read out over one neighbour on either side."""
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
            "read_out_contact": [{"name": "top", "x_span": 1, "y_span": 0}],
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


@pytest.mark.devsim
def test_a_cell_laid_side_by_side_is_the_mesh_of_the_row_with_the_listed_electrode_in_the_middle() -> (
    None
):
    import devsim

    from raser.core.field.create_mesh import DevsimMesh

    try:
        DevsimMesh(_strips(3), WEIGHTING).create2DMesh()
        whole = {tuple(place) for place in _nodes()}
        devsim.reset_devsim()

        DevsimMesh(_strips(1), WEIGHTING, cells_either_side=1).createRowOfCells()
        row = _nodes()
        contacts = set(devsim.get_contact_list(device="slab"))
        read_out, neighbours, back = _nodes("top"), _nodes("neighbours"), _nodes("bot")
    finally:
        devsim.reset_devsim()

    # the nodes two cells share are there once
    assert len(row) == len(whole)
    assert {tuple(place) for place in row} == whole
    assert contacts == {"top", "neighbours", "bot"}
    assert sorted(read_out[:, 1]) == [5.0, 6.0, 7.0]
    assert sorted(neighbours[:, 1]) == [1.0, 2.0, 3.0, 9.0, 10.0, 11.0]
    assert sorted(back[:, 1]) == list(np.arange(0.0, 13.0))


@pytest.mark.devsim
def test_a_mesh_that_is_not_one_pitch_wide_is_not_laid_side_by_side() -> None:
    import devsim

    from raser.core.field.create_mesh import DevsimMesh

    device = _strips(1)
    device.p_x = 5.0
    try:
        with pytest.raises(ValueError, match="4 um wide, not one pitch of 5 um"):
            DevsimMesh(device, WEIGHTING, cells_either_side=1).createRowOfCells()
    finally:
        devsim.reset_devsim()
