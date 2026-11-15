from __future__ import annotations

import json
import pickle
from pathlib import Path

import pytest

from raser.core.field.devsim_field import DevsimField

FILES = {
    "Potential_57V.pkl": "potential",
    "NetDoping_0V.pkl": "net doping",
    "TrappingRate_p_57V.pkl": "hole trapping rate",
    "TrappingRate_n_57V.pkl": "electron trapping rate",
    "weightingfield/top/Potential_57V.pkl": "weighting potential of top",
    "Conductive_57V.pkl": "conductive part",
}


def _solved(folder: Path, axes: list[str]) -> None:
    """A one-dimensional field at 57 V with everything a solve leaves."""
    for name in FILES:
        (folder / name).parent.mkdir(parents=True, exist_ok=True)
        stored = {
            "points": [0.0, 0.005],
            "values": [0.0, 57.0],
            "metadata": {"dimension": 1},
        }
        (folder / name).write_bytes(pickle.dumps(stored))
    (folder / "run.json").write_text(json.dumps({"axes": axes}))


def _field(folder: Path) -> DevsimField:
    return DevsimField("device", 57, [{"name": "top"}], field_directory=folder)


@pytest.mark.parametrize("name", FILES)
def test_a_field_with_a_part_missing_is_not_loaded(tmp_path: Path, name: str) -> None:
    _solved(tmp_path, ["z"])
    assert _field(tmp_path).get_potential(0.0, 0.0, 25.0) == pytest.approx(28.5)

    (tmp_path / name).unlink()
    with pytest.raises(FileNotFoundError, match=f"the {FILES[name]} of device at 57 V"):
        _field(tmp_path)


def test_a_field_stored_in_fewer_dimensions_than_its_axes_is_not_loaded(
    tmp_path: Path,
) -> None:
    _solved(tmp_path, ["z", "x"])

    with pytest.raises(ValueError, match="has 1 dimensions, the field has 2"):
        _field(tmp_path)


def test_a_position_conducts_when_every_node_of_its_cell_does(
    tmp_path: Path,
) -> None:
    _solved(tmp_path, ["z"])
    nodes = {"points": [0.0, 0.001, 0.004, 0.005], "values": [1.0, 1.0, 0.0, 0.0]}
    (tmp_path / "Conductive_57V.pkl").write_bytes(
        pickle.dumps({**nodes, "metadata": {"dimension": 1}})
    )
    field = _field(tmp_path)

    # nodes at 0, 10, 40 and 50 um: the first two conduct
    assert field.get_conductive(0.0, 0.0, 5.0)
    # the interval from 10 to 40 um has one node that does not conduct
    assert not field.get_conductive(0.0, 0.0, 12.0)
    assert not field.get_conductive(0.0, 0.0, 26.0)
    assert not field.get_conductive(0.0, 0.0, 45.0)
    assert field.get_conductive(0.0, 0.0, -3.0)
    assert not field.get_conductive(0.0, 0.0, 58.0)


def _along_x(folder: Path, name: str, cells: int) -> None:
    """A stored quantity on a mesh of depth and x, 50 um deep and `cells`
    cells of 100 um wide, whose value is the place along x in um."""
    across = [0.0025 * step for step in range(4 * cells + 1)]
    stored = {
        "points": [[depth, x] for depth in (0.0, 0.0025, 0.005) for x in across],
        "values": [x * 1e4 for _ in range(3) for x in across],
        "metadata": {"dimension": 2},
    }
    (folder / name).write_bytes(pickle.dumps(stored))


@pytest.mark.parametrize("cells_of_the_field", [1, 3])
def test_the_electric_field_of_a_row_is_read_in_one_cell(
    tmp_path: Path, cells_of_the_field: int
) -> None:
    _solved(tmp_path, ["z", "x"])
    for name in FILES:
        _along_x(tmp_path, name, 3 if "weightingfield" in name else cells_of_the_field)
    field = DevsimField(
        "device",
        57,
        [{"name": "top", "x_span": 1, "y_span": 0}],
        bounds={"x": [0.0, 1000.0], "z": [0.0, 50.0]},
        field_directory=tmp_path,
    )

    # ten cells of 100 um: a place is read as far into the cell of the field
    # as it is into its own, the middle one where the field holds three
    first = 100.0 * (cells_of_the_field // 2)
    assert field.get_potential(30.0, 0.0, 25.0) == pytest.approx(first + 30.0)
    assert field.get_potential(250.0, 0.0, 25.0) == pytest.approx(first + 50.0)
    assert field.get_potential(970.0, 0.0, 25.0) == pytest.approx(first + 70.0)
