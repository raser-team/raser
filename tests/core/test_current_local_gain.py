"""Gain along the drift paths, in fields of more than one dimension."""

from types import SimpleNamespace

import pytest

from raser.core.current.cal_current import CalCurrent

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
