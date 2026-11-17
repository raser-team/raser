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

    assert sum(current.gain_current.hole_system.carriers) == pytest.approx(expected, rel=1e-6)
    assert len(current.gain_current.hole_system.carriers) == 6
    # each path's pairs start on its last step: the electrons' near z = 0, the holes' near 50 um
    births = sorted(float(path[0][2]) for path in current.gain_current.hole_system.paths)
    assert max(births[:3]) < 3.0 and min(births[3:]) > 47.0


class _ThinLayer(_Field):
    """Gain only between z = 10 and 11 um: an electron from the top face multiplies once."""

    def get_e_field_cached(self, x, y, z):
        return (0.0, 0.0, 3e5 if 10.0 < z < 11.0 else 5e4)


def test_a_gain_that_needs_more_slices_than_places_left_stops_with_an_error() -> None:
    # one emission of four slices, with one place left: not one cluster in their stead
    with pytest.raises(ValueError, match="gain_max_carriers = 1"):
        CalCurrent(
            _device(gain_max_carriers=1, local_gain_emit_slices=4), _ThinLayer(),
            [100.0], [[50.0, 50.0, 50.0, 0.0]], diffusion=False,
        )


def test_a_gain_that_needs_exactly_the_allowed_clusters_is_made_whole() -> None:
    current = CalCurrent(
        _device(gain_max_carriers=4, local_gain_emit_slices=4), _ThinLayer(),
        [100.0], [[50.0, 50.0, 50.0, 0.0]], diffusion=False,
    )

    births = sorted(float(path[0][2]) for path in current.gain_current.hole_system.paths)
    assert len(births) == 4
    assert births[-1] - births[0] > 0.5


class _TwoLayers(_Field):
    """Gain between z = 30 and 32 um and between 10 and 12 um, little elsewhere."""

    def get_e_field_cached(self, x, y, z):
        return (0.0, 0.0, FIELD if 10.0 < z < 12.0 or 30.0 < z < 32.0 else 5e4)


def test_gain_pairs_too_few_to_emit_start_in_the_layer_they_grew_in() -> None:
    # an electron from the top face multiplies in both layers, each time by
    # fewer pairs than the threshold: each layer's pairs start in that layer
    current = CalCurrent(
        _device(gain_pair_threshold=1e30), _TwoLayers(), [1.0], [[50.0, 50.0, 50.0, 0.0]], diffusion=False
    )

    gain = current.gain_current.hole_system
    births = sorted((float(path[0][2]), charge) for charge, path in zip(gain.carriers, gain.paths))
    assert len(births) == 2
    assert 9.0 < births[0][0] < 12.5 and 29.0 < births[1][0] < 32.5
