"""The share of a laser pulse in each time bin, which the currents are convolved with."""

import math

import numpy as np
import pytest

from raser.core.current.cal_current import pulse_in_bins


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
