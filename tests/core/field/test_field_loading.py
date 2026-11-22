from __future__ import annotations

import json
import pickle
from pathlib import Path

import numpy as np
import pytest

from raser.core.field.devsim_field import DevsimField
from raser.core.field.interpolation import interpolate_3d

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
        # the weighting potential is on five cells: the cell is the pitch,
        # whatever the width of the mesh of the weighting potential
        _along_x(tmp_path, name, 5 if "weightingfield" in name else cells_of_the_field)
    field = DevsimField(
        "device",
        57,
        [{"name": "top", "x_span": 1, "y_span": 0}],
        bounds={"x": [0.0, 1000.0], "z": [0.0, 50.0]},
        field_directory=tmp_path,
        pitch={"x": 100.0},
    )

    # ten cells of 100 um: a place is read as far into the cell of the field
    # as it is into its own, the middle one where the field holds three
    first = 100.0 * (cells_of_the_field // 2)
    assert field.get_potential(30.0, 0.0, 25.0) == pytest.approx(first + 30.0)
    assert field.get_potential(250.0, 0.0, 25.0) == pytest.approx(first + 50.0)
    assert field.get_potential(970.0, 0.0, 25.0) == pytest.approx(first + 70.0)


@pytest.mark.parametrize(
    ("pitch_um", "said"),
    [
        (120.0, "less than the pitch"),  # the mesh of 100 um does not hold one cell
        (80.0, "whole number of pitches"),  # 1.25 cells: no cell to take a place back into
    ],
)
def test_a_field_whose_mesh_does_not_fit_the_pitch_is_not_loaded(
    tmp_path: Path, pitch_um: float, said: str
) -> None:
    _solved(tmp_path, ["z", "x"])
    for name in FILES:
        _along_x(tmp_path, name, 1)

    with pytest.raises(ValueError, match=said):
        DevsimField(
            "device",
            57,
            [{"name": "top"}],
            bounds={"x": [0.0, 1000.0], "z": [0.0, 50.0]},
            field_directory=tmp_path,
            pitch={"x": pitch_um},
        )


def test_unstructured_3d_field_is_regularized_with_explicit_bins() -> None:
    points = np.asarray(
        [
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (0.0, 0.0, 1.0),
            (1.0, 1.0, 1.0),
        ]
    )
    values = np.sum(points, axis=1)
    interpolation = interpolate_3d(
        {"points": points, "values": values},
        bins={"x": 5, "y": 5, "z": 5},
    )

    assert interpolation(0.0, 0.0, 0.0) == pytest.approx(0.0)
    assert interpolation(1.0, 1.0, 1.0) == pytest.approx(3.0)
    assert 0.0 < interpolation(0.5, 0.5, 0.5) < 3.0


def test_repeated_3d_points_do_not_leave_an_uninitialized_grid_cell() -> None:
    points = np.asarray(
        [
            (0.0, 0.0, 0.0),
            (0.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (0.0, 0.0, 1.0),
            (0.0, 1.0, 1.0),
            (1.0, 0.0, 0.0),
            (1.0, 1.0, 0.0),
            (1.0, 0.0, 1.0),
        ]
    )
    interpolation = interpolate_3d(
        {"points": points, "values": np.sum(points, axis=1)},
        bins={"x": 3, "y": 3, "z": 3},
    )

    assert np.isfinite(interpolation(1.0, 1.0, 1.0))


def _write_field_pickle(path: Path, points, values, *, voltage: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as stream:
        pickle.dump(
            {
                "points": np.asarray(points, dtype=float),
                "values": np.asarray(values, dtype=float),
                "metadata": {"voltage": voltage, "dimension": 3},
            },
            stream,
        )


def test_devsim_field_loads_unstructured_3d_assets(tmp_path: Path) -> None:
    points = np.asarray(
        [
            (0.0, 0.0, 0.0),
            (0.01, 0.0, 0.0),
            (0.0, 0.01, 0.0),
            (0.0, 0.0, 0.01),
            (0.01, 0.01, 0.01),
        ]
    )
    potential = np.sum(points, axis=1)
    _write_field_pickle(tmp_path / "Potential_57V.pkl", points, potential, voltage=57)
    _write_field_pickle(
        tmp_path / "NetDoping_0V.pkl", points, np.full(5, 1.0e12), voltage=0
    )
    _write_field_pickle(
        tmp_path / "TrappingRate_p_57V.pkl", points, np.zeros(5), voltage=57
    )
    _write_field_pickle(
        tmp_path / "TrappingRate_n_57V.pkl", points, np.zeros(5), voltage=57
    )
    _write_field_pickle(
        tmp_path / "Conductive_57V.pkl", points, np.zeros(5), voltage=57
    )
    _write_field_pickle(
        tmp_path / "weightingfield" / "center" / "Potential_57V.pkl",
        points,
        potential / 0.03,
        voltage=1,
    )

    (tmp_path / "run.json").write_text(json.dumps({"axes": ["x", "y", "z"]}))

    field = DevsimField(
        "synthetic-3d",
        57,
        [{"name": "center"}],
        bounds={"x": (0.0, 100.0), "y": (0.0, 100.0), "z": (0.0, 100.0)},
        field_directory=tmp_path,
    )

    assert field.get_potential(0.0, 0.0, 0.0) == pytest.approx(0.0)
    assert field.get_potential(100.0, 100.0, 100.0) == pytest.approx(0.03)
    assert field.get_w_p(100.0, 100.0, 100.0, 0) == pytest.approx(1.0)
    assert np.all(np.isfinite(field.get_e_field(50.0, 50.0, 50.0)))


def _write_field(directory: Path, points, potential, axes) -> None:
    flat = np.zeros(len(points))
    for name, values, voltage in (
        ("Potential_57V.pkl", potential, 57),
        ("NetDoping_0V.pkl", flat, 0),
        ("TrappingRate_p_57V.pkl", flat, 57),
        ("TrappingRate_n_57V.pkl", flat, 57),
        ("Conductive_57V.pkl", flat, 57),
        ("weightingfield/center/Potential_57V.pkl", flat, 1),
    ):
        _write_field_pickle(directory / name, points, values, voltage=voltage)
    if axes:
        (directory / "run.json").write_text(json.dumps({"axes": list(axes)}))


def _grid_3d():
    grid = np.linspace(0.0, 0.01, 3)
    return np.array([(a, b, c) for a in grid for b in grid for c in grid])


@pytest.mark.parametrize(
    ("axes", "along"),
    [(("x", "y", "z"), 0), (("z", "x", "y"), 1)],
)
def test_a_field_is_read_along_the_axes_its_folder_records(
    tmp_path: Path, axes, along
) -> None:
    points = _grid_3d()
    _write_field(tmp_path, points, 100.0 * points[:, along], axes)

    field = DevsimField("synthetic", 57, [{"name": "center"}], field_directory=tmp_path)

    assert field.get_potential(100.0, 50.0, 50.0) == pytest.approx(1.0)
    assert field.get_potential(0.0, 50.0, 50.0) == pytest.approx(0.0)
    assert field.get_e_field(50.0, 50.0, 50.0) == pytest.approx((-100.0, 0.0, 0.0))


def test_a_field_folder_without_its_record_is_refused(tmp_path: Path) -> None:
    points = _grid_3d()
    _write_field(tmp_path, points, points[:, 0], axes=None)

    with pytest.raises(FileNotFoundError, match="run.json is missing"):
        DevsimField("synthetic", 57, [{"name": "center"}], field_directory=tmp_path)
