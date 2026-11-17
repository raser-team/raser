"""Gain along the drift paths, in fields of more than one dimension."""

import math
from types import SimpleNamespace

import pytest

from raser.core.current.cal_current import CalCurrent
from raser.core.model.material import Material

FIELD = 2.2e5  # V/cm along z, above the threshold of the van Overstraeten - de Man model


class _Field:
    """A uniform field stored in x and z, so that the gain is taken along the paths."""

    axes = ("x", "z")
    cells_either_side = 0

    def get_e_field_cached(self, x, y, z):
        return (0.0, 0.0, FIELD)

    def get_doping_cached(self, x, y, z):
        return 0.0

    def get_conductive(self, x, y, z):
        return False

    def get_w_p(self, x, y, z, electrode):
        return 1.0 - z / 50.0


def _device(**changes):
    device = dict(
        dimension=2, is_plugin=lambda: False, material="Si", temperature=300.0,
        l_x=100.0, l_y=100.0, l_z=50.0, p_x=100.0, p_y=100.0, x_ele_num=1, y_ele_num=1,
        read_ele_num=1, read_out_contact=[{"x_span": 0, "y_span": 0, "name": "top"}],
        irradiation_model=None, det_model="planar", voltage=200.0, has_avalanche=True,
        avalanche_model="vanOverstraeten", det_name="uniform",
    )
    device.update(changes)
    return SimpleNamespace(**device)


STARTS = [[50.0, 50.0, z, 0.0] for z in (10.0, 25.0, 40.0)]
PAIRS = [100.0, 100.0, 100.0]


def test_a_gain_that_needs_more_clusters_than_allowed_stops_with_an_error() -> None:
    with pytest.raises(ValueError, match="gain_max_carriers = 1"):
        CalCurrent(_device(gain_max_carriers=1), _Field(), PAIRS, STARTS, diffusion=False)


def test_pairs_too_few_to_emit_on_the_way_are_emitted_at_the_end_of_the_path() -> None:
    # with a threshold no segment reaches, every gain pair is still made: each
    # electron multiplies over the depth z it drifts, each hole over 50 um - z
    alpha = Material("Si", avalanche_model="vanOverstraeten").cal_coefficient
    expected = sum(
        pairs * math.expm1(alpha(FIELD, -1, 300.0) * z * 1e-4)
        + pairs * math.expm1(alpha(FIELD, 1, 300.0) * (50.0 - z) * 1e-4)
        for pairs, (_, _, z, _) in zip(PAIRS, STARTS)
    )

    current = CalCurrent(_device(gain_pair_threshold=1e30), _Field(), PAIRS, STARTS, diffusion=False)

    assert sum(current.gain_current.hole_system.charges) == pytest.approx(expected, rel=1e-6)
    assert len(current.gain_current.hole_system.charges) == 6
