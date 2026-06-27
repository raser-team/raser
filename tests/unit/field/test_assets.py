import pickle

import numpy as np

from raser.core.field import assets
from raser.core.field import weighting_potential


def _write_field(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "values": values,
        "points": [0.0, 1.0],
        "metadata": {"dimension": 1, "voltage": 200},
    }
    with open(path, "wb") as file:
        pickle.dump(data, file)


def test_voltage_label_normalizes_numeric_values():
    assert assets.voltage_label("200") == "200"
    assert assets.voltage_label(200.0) == "200"
    assert assets.voltage_label("0.5") == "0.5"


def test_resolve_field_pickle_matches_equivalent_voltage_names(tmp_path):
    field = tmp_path / "Potential_200.0V.pkl"
    field.write_text("field", encoding="utf-8")

    assert assets.resolve_field_pickle(tmp_path, "Potential", 200) == field
    assert assets.resolve_field_pickle(tmp_path, "Potential", "200") == field


def test_weighting_potential_uses_numeric_voltage_resolution(tmp_path, monkeypatch):
    monkeypatch.setenv("RASER_PROJECT_PATH", str(tmp_path))
    field_root = tmp_path / "field" / "default"
    weighting_root = field_root / "weightingfield" / "top"
    _write_field(field_root / "Potential_200V.pkl", np.array([1.0, 2.0]))
    _write_field(weighting_root / "Potential_200.0V.pkl", np.array([3.0, 5.0]))
    monkeypatch.setattr(weighting_potential.devsim_draw, "draw1D", lambda *args: None)

    weighting_potential.main("200", "top", "HPK-Si-PiN")

    with open(weighting_root / "Potential_1V.pkl", "rb") as file:
        result = pickle.load(file)
    assert result["metadata"] == {"dimension": 1, "voltage": 1}
    assert result["values"].tolist() == [2.0, 3.0]
