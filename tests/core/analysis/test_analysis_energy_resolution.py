import numpy as np
import pytest

from raser.core.analysis.resolution import FWHM_OVER_SIGMA
from raser.core.analysis.resolution import NoSpread
from raser.core.analysis.resolution import TooFewValues
from raser.core.analysis.resolution import fwhm_over_mean
from raser.core.analysis.resolution import mad_core_resolution

MEAN, SIGMA = 50.0, 3.0


def test_gaussian_sample_gives_fwhm_of_the_gaussian_over_its_mean() -> None:
    n = 100000
    values = np.random.default_rng(1).normal(MEAN, SIGMA, n)

    result = fwhm_over_mean(values)

    # sigma / sigma_hat has the relative error 1 / sqrt(2 n); the mean's is 1e-3 of it
    expected = 2.3548 * SIGMA / MEAN
    assert result["events"] == n
    assert result["resolution"] == pytest.approx(expected, rel=5 / np.sqrt(2 * n))
    assert FWHM_OVER_SIGMA == pytest.approx(2.3548, abs=5e-5)


def test_resolution_does_not_depend_on_the_unit_of_the_values() -> None:
    values = np.random.default_rng(2).normal(MEAN, SIGMA, 1000)

    assert fwhm_over_mean(1e-3 * values)["resolution"] == pytest.approx(fwhm_over_mean(values)["resolution"], rel=1e-12)


def test_far_outliers_leave_the_core_resolution_and_widen_the_plain_one() -> None:
    n = 20000
    clean = np.random.default_rng(3).normal(MEAN, SIGMA, n)
    values = np.concatenate([clean, np.full(n // 100, 5 * MEAN)])  # 1 % at 5 times the mean

    plain = fwhm_over_mean(values)["resolution"]
    result = mad_core_resolution(values)

    expected = 2.3548 * SIGMA / MEAN
    assert plain > 3 * expected
    # the cut at 5 sigma_MAD loses 6e-7 of a Gaussian: what is left is the Gaussian
    assert result["core_resolution"] == pytest.approx(expected, rel=0.03)
    assert result["core_events"] == n
    assert result["events"] == n + n // 100
    # sigma_MAD of the whole sample, in which the outliers are 1 %, is that of the Gaussian
    assert result["mad_sigma"] == pytest.approx(SIGMA, rel=0.03)
    assert result["resolution"] == pytest.approx(plain)


def test_core_holds_the_values_within_five_sigma_mad_of_the_median() -> None:
    # median 10, MAD 1, sigma_MAD 1.4826: the core is [10 - 7.413, 10 + 7.413]
    values = np.array([9.0, 10.0, 10.0, 11.0, 10.0, 9.0, 11.0, 17.4, 2.6, 17.5, 2.5])

    result = mad_core_resolution(values)

    assert result["median"] == 10.0
    assert result["mad_sigma"] == pytest.approx(1.4826)
    assert result["core_events"] == 9  # 17.5 and 2.5 are outside
    assert result["core_mean"] == pytest.approx(np.mean([9, 10, 10, 11, 10, 9, 11, 17.4, 2.6]))


@pytest.mark.parametrize("function", [fwhm_over_mean, mad_core_resolution])
@pytest.mark.parametrize("count", [0, 1])
def test_fewer_than_two_values_are_too_few(function, count) -> None:
    with pytest.raises(TooFewValues):
        function(np.full(count, 5.0))


def test_a_median_that_most_values_share_has_no_core() -> None:
    with pytest.raises(NoSpread):
        mad_core_resolution(np.array([5.0, 5.0, 5.0, 6.0, 9.0]))


def test_values_that_are_not_finite_or_have_mean_zero_are_errors() -> None:
    with pytest.raises(ValueError, match="not finite"):
        fwhm_over_mean(np.array([1.0, np.nan, 2.0]))
    with pytest.raises(ValueError, match="mean of the values is 0"):
        fwhm_over_mean(np.array([-1.0, 1.0]))


def test_sigma_is_the_population_standard_deviation() -> None:
    result = fwhm_over_mean(np.array([1.0, 2.0, 3.0]))

    assert result["mean"] == 2.0
    assert result["sigma"] == pytest.approx(np.sqrt(2 / 3))
    assert result["resolution"] == pytest.approx(FWHM_OVER_SIGMA * np.sqrt(2 / 3) / 2.0)
