import json

import numpy as np

from raser.stages.analysis.across_points import write_points
from raser.stages.analysis.collection import energy_resolution


def _result(rng, width):
    charge = rng.normal(100.0, width, 500)
    values = np.concatenate([charge, np.full(5, 1000.0)])
    return {
        "collection": {"events": 505, "mean": 0.9, "mean_error": 0.01},
        "timing": {"selected": 3},
        "energy_resolution": {"charge": energy_resolution(values), "amplitude": energy_resolution(values[:1])},
    }


def test_points_hold_both_resolutions_of_each_quantity_that_has_one(tmp_path) -> None:
    rng = np.random.default_rng(5)
    results = [_result(rng, 2.0), _result(rng, 4.0)]
    points = [("voltage_100", {"field.voltage": 100}), ("voltage_200", {"field.voltage": 200})]

    write_points(points, results, tmp_path)

    rows = json.loads((tmp_path / "points.json").read_text())
    for row, result in zip(rows, results):
        assert set(row["energy_resolution"]) == {"charge"}  # one value has no width
        assert row["energy_resolution"]["charge"] == {
            key: result["energy_resolution"]["charge"][key] for key in ("resolution", "core_resolution")
        }
    # the outliers are in the plain resolution only, and a wider core is a worse resolution
    first, second = (row["energy_resolution"]["charge"] for row in rows)
    assert second["core_resolution"] > 1.5 * first["core_resolution"]
    assert first["resolution"] > 3 * first["core_resolution"]
    assert (tmp_path / "energy_resolution.png").exists()
    assert (tmp_path / "energy_resolution.pdf").exists()
