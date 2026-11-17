"""The gain current is binned on the time axis of the current it multiplies."""

import math
from types import SimpleNamespace

import pytest

from raser.core.current.cal_current import CalCurrent

GAIN = 3.0


class _UniformField:
    """10 kV/cm along z; weighting potential falls linearly from z = 0."""

    cells_either_side = 0

    axes = ("z",)

    def get_e_field_cached(self, x, y, z):
        return (0.0, 0.0, 1.0e4)

    def get_doping_cached(self, x, y, z):
        return 0.0

    def get_conductive(self, x, y, z):
        return False

    def get_w_p(self, x, y, z, electrode):
        return 1.0 - z / 50.0

    def get_cache_stats(self):
        return {"hits": 0, "misses": 0, "errors": 0, "fallbacks": 0, "hit_rate": 0.0}

    def planar_gain(self, my_d):
        return GAIN

    def planar_gain_at(self, my_d, z):
        return GAIN

    def planar_gain_depth(self, my_d):
        return 1.0

    def planar_gain_carrier(self, my_d):
        return -1


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


def test_bins_are_as_wide_as_the_written_bin_width_when_deposits_are_spread_in_time():
    # 3.3 ps apart: the window of 6.25 ns after the first is not a whole
    # number of 5 ps bins; it is lengthened to one, not spread over them
    current = CalCurrent(
        _lgad(),
        _UniformField(),
        [100.0, 100.0],
        [[50.0, 50.0, 25.0, 0.0], [50.0, 50.0, 25.0, 3.3e-12]],
    )

    assert current.t_bin == 5e-12
    assert (current.t_end - current.t_start) / current.n_bin == pytest.approx(5e-12, rel=1e-12, abs=0)
    assert current.n_bin == 1251
    assert current.t_end >= 3.3e-12 + 5e-9


def test_the_window_reaches_5_ns_after_a_deposit_a_hair_later_than_the_first():
    # 2 attoseconds apart: 1250 bins would end 2 as short of 5 ns after the last
    current = CalCurrent(
        SimpleNamespace(**{**vars(_lgad()), "has_avalanche": False}),
        _UniformField(),
        [100.0, 100.0],
        [[50.0, 50.0, 25.0, 0.0], [50.0, 50.0, 25.0, 2e-18]],
    )

    assert current.t_end >= 2e-18 + 5e-9
    assert current.t_end - current.t_bin < 2e-18 + 5e-9


class _ConductingBelow10um(_UniformField):
    def get_conductive(self, x, y, z):
        return z < 10.0


def test_sensitive_pairs_leave_out_the_pairs_born_where_the_device_conducts():
    # 100 pairs at z = 5 um, in the conducting layer, stop where they are born;
    # 40 at 25 um and 60 at 40 um drift; 7 above the device are not drifted at all
    current = CalCurrent(
        SimpleNamespace(**{**vars(_lgad()), "has_avalanche": False}),
        _ConductingBelow10um(),
        [100.0, 40.0, 60.0, 7.0],
        [[50.0, 50.0, 5.0, 0.0], [50.0, 50.0, 25.0, 0.0], [50.0, 50.0, 40.0, 0.0], [50.0, 50.0, 60.0, 0.0]],
    )

    assert current.pairs == 207.0
    assert current.sensitive_pairs == 100.0


class _Trapping(_UniformField):
    """Electrons and holes trapped at 2e9 /s everywhere."""

    def get_trap_e_cached(self, x, y, z):
        return 2.0e9

    def get_trap_h_cached(self, x, y, z):
        return 2.0e9


def test_the_planar_gain_multiplies_the_electrons_left_when_they_reach_the_gain_layer():
    # electrons from z = 25 um reach the gain layer at z = 0 after t; of 100,
    # 100 exp(-2e9 t) are left to multiply by GAIN
    current = CalCurrent(
        SimpleNamespace(**{**vars(_lgad()), "irradiation_model": "constant"}),
        _Trapping(),
        [100.0],
        [[50.0, 50.0, 25.0, 0.0]],
        diffusion=False,
    )

    electron = current.electron_system.paths[0]
    arrival = electron[-1][3]
    made = sum(current.gain_current.hole_system.carriers)
    assert made == pytest.approx(GAIN * 100.0 * math.exp(-2.0e9 * arrival), rel=2e-3)
    assert made < 0.8 * GAIN * 100.0
