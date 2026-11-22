"""The share of a laser pulse in each time bin, which the currents are convolved with."""

import math

import numpy as np
import pytest

import sys
from pathlib import Path
from types import SimpleNamespace

from raser.core.current.cal_current import CalCurrent, CalCurrentLaser, pulse_in_bins

sys.path.insert(0, str(Path(__file__).parent))
from test_current_gain_time_axis import _lgad, _UniformField  # noqa: E402


def _gaussian(fwhm):
    sigma = fwhm / (2 * math.sqrt(2 * math.log(2)))
    return lambda t: np.exp(-(t**2) / (2 * sigma**2)) / (math.sqrt(2 * math.pi) * sigma), sigma


def test_a_pulse_much_shorter_than_a_bin_lies_whole_in_the_bin_of_its_middle() -> None:
    # 60 fs in bins of 5 ps: sampled at the middle of the bin it would give 78
    pulse, _ = _gaussian(60e-15)

    shares = pulse_in_bins(pulse, 60e-15, 100, 5e-12)

    assert shares[99] == pytest.approx(1.0, rel=1e-6)
    assert shares.sum() == pytest.approx(1.0, rel=1e-6)


def test_a_pulse_wider_than_a_bin_shares_as_the_integral_of_its_gaussian() -> None:
    # 8 ps in bins of 5 ps: sampled at the middle of each bin it would be
    # 7 % too high in the middle bin
    pulse, sigma = _gaussian(8e-12)

    shares = pulse_in_bins(pulse, 8e-12, 100, 5e-12)

    def below(t):
        return 0.5 * (1 + math.erf(t / (math.sqrt(2) * sigma)))

    for k in (0, 1, 2):
        assert shares[99 + k] == pytest.approx(below((k + 0.5) * 5e-12) - below((k - 0.5) * 5e-12), rel=1e-2)
    assert shares.sum() == pytest.approx(1.0, rel=1e-6)


def test_the_current_of_a_laser_pulse_is_spread_over_the_pulse_and_keeps_its_charge() -> None:
    # pairs made by a pulse of 100 ps FWHM centred on t = 0: each part of the
    # current of pairs made at once comes earlier or later by the width of the
    # pulse. The window opens and closes the reach of the pulse beyond the
    # drift, so the whole charge stays in it, and the charge before 50 ps is
    # that of each bin of the current made at once times the chance that the
    # pulse moved it to before 50 ps
    pulse, sigma = _gaussian(100e-12)
    laser = SimpleNamespace(
        ionized_pairs=[100.0], track_position=[[50.0, 50.0, 25.0, 0.0]],
        timePulse=pulse, temporal_FWHM=100e-12,
    )
    device = SimpleNamespace(**{**vars(_lgad()), "has_avalanche": False})

    spread = CalCurrentLaser(device, _UniformField(), laser, diffusion=False)
    at_once = CalCurrent(device, _UniformField(), [100.0], [[50.0, 50.0, 25.0, 0.0]], diffusion=False)

    times = spread.t_start + (np.arange(spread.n_bin) + 0.5) * spread.t_bin
    collected = spread.current[0].sum() * spread.t_bin
    early = spread.current[0][times < 50e-12].sum() * spread.t_bin

    def below(t):
        return 0.5 * (1 + math.erf(t / (math.sqrt(2) * sigma)))

    at_once_times = at_once.t_start + (np.arange(at_once.n_bin) + 0.5) * at_once.t_bin
    chance = np.array([below(50e-12 - t) for t in at_once_times])
    expected = (at_once.current[0] * chance).sum() * at_once.t_bin
    assert spread.t_start < at_once.t_start
    assert collected == pytest.approx(at_once.current[0].sum() * at_once.t_bin, rel=1e-6, abs=0)
    assert early == pytest.approx(expected, rel=0.03, abs=0)
    assert early / collected > 1e-3
