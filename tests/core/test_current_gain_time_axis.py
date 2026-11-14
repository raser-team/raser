"""The gain current is binned on the time axis of the current it multiplies."""

from types import SimpleNamespace

import pytest

from raser.core.current.cal_current import CalCurrent

GAIN = 3.0


class _UniformField:
    """10 kV/cm along z; weighting potential falls linearly from z = 0."""

    axes = ("z",)

    def get_e_field_cached(self, x, y, z):
        return (0.0, 0.0, 1.0e4)

    def get_doping_cached(self, x, y, z):
        return 0.0

    def get_w_p(self, x, y, z, electrode):
        return 1.0 - z / 50.0

    def get_cache_stats(self):
        return {"hits": 0, "misses": 0, "errors": 0, "fallbacks": 0, "hit_rate": 0.0}

    def planar_gain(self, my_d):
        return GAIN


def _lgad():
    return SimpleNamespace(
        dimension=1,
        is_plugin=lambda: False,
        material="Si",
        temperature=300.0,
        l_x=100.0,
        l_y=100.0,
        l_z=50.0,
        p_x=100.0,
        p_y=100.0,
        x_ele_num=1,
        y_ele_num=1,
        read_ele_num=1,
        read_out_contact=[{"x_span": 0, "y_span": 0, "name": "top"}],
        irradiation_model=None,
        det_model="planar",
        voltage=200.0,
        has_avalanche=True,
        avalanche_bond=1.0,
    )


def _charge(histogram):
    return histogram.Integral() * histogram.GetBinWidth(1)


def test_gain_current_adds_to_a_current_whose_deposits_are_spread_in_time():
    # two deposits a few ps apart, as a laser pulse or a particle track gives
    current = CalCurrent(
        _lgad(),
        _UniformField(),
        [100.0, 100.0],
        [[50.0, 50.0, 25.0, 0.0], [50.0, 50.0, 25.0, 3.3e-12]],
    )

    total = current.sum_cu[0]
    gain = current.gain_current
    assert total.GetNbinsX() == current.n_bin
    assert total.GetXaxis().GetXmin() == pytest.approx(current.t_start)
    assert total.GetXaxis().GetXmax() == pytest.approx(current.t_end)
    assert _charge(total) == pytest.approx(
        _charge(current.positive_cu[0])
        + _charge(current.negative_cu[0])
        + _charge(gain.positive_cu[0])
        + _charge(gain.negative_cu[0]),
        rel=1e-6,
        abs=0.0,
    )
    assert _charge(gain.positive_cu[0]) != 0.0
