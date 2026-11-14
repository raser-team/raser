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
    "weightingfield/top/Potential_1V.pkl": "weighting potential of top",
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
    assert _field(tmp_path)._get_potential(0.0, 0.0, 25.0) == pytest.approx(28.5)

    (tmp_path / name).unlink()
    with pytest.raises(FileNotFoundError, match=f"the {FILES[name]} of device at 57 V"):
        _field(tmp_path)


def test_a_field_stored_in_fewer_dimensions_than_its_axes_is_not_loaded(
    tmp_path: Path,
) -> None:
    _solved(tmp_path, ["z", "x"])

    with pytest.raises(ValueError, match="has 1 dimensions, the field has 2"):
        _field(tmp_path)
