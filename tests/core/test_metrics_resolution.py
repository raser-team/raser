import numpy as np
import pytest

from raser.core.metrics.resolution import core_width, truncated_gaussian


def test_values_inside_one_sigma_give_the_width_of_the_whole_gaussian() -> None:
    values = np.random.default_rng(1).normal(5.0, 30.0, 200000)
    inside = values[(values >= -25.0) & (values <= 35.0)]
    assert np.std(inside) < 17.0  # what is inside is much narrower than 30

    mean, mean_error, sigma, sigma_error = truncated_gaussian(inside, -25.0, 35.0)

    assert mean == pytest.approx(5.0, abs=5 * mean_error)
    assert sigma == pytest.approx(30.0, abs=5 * sigma_error)
    # the cut costs information: 4.8 times the sigma / sqrt(2 N) of an uncut sample
    assert sigma_error == pytest.approx(4.8 * 30.0 / np.sqrt(2 * len(inside)), rel=0.05)


def test_fit_of_a_tail_without_a_core_keeps_its_mean_inside_the_window() -> None:
    # values that only rise towards the upper edge: a Gaussian far beyond
    # it with a large sigma fits them best, unless the mean is held inside
    values = 1.0 + np.log(np.random.default_rng(4).uniform(np.exp(-3.0), 1.0, 2000)) / 3.0

    mean, _, sigma, _ = truncated_gaussian(values, 0.0, 1.0)

    assert 0.0 <= mean <= 1.0
    assert sigma < 1.0


def test_core_width_is_the_width_of_the_core_under_a_wide_tail() -> None:
    rng = np.random.default_rng(2)
    values = np.concatenate([rng.normal(100.0, 30.0, 20000), rng.normal(100.0, 600.0, 4000)])
    assert np.std(values) > 200.0

    width = core_width(values)

    # a tenth of the tail lies under the core and widens it by a few percent
    assert width["sigma"] == pytest.approx(31.0, abs=1.5)
    assert width["mean"] == pytest.approx(100.0, abs=1.0)
    low, high = width["window"]
    assert low == pytest.approx(width["mean"] - 2 * width["sigma"], rel=0.02)
    assert high == pytest.approx(width["mean"] + 2 * width["sigma"], rel=0.02)
    # a Gaussian cut at +-2 sigma has its 16 % and 84 % at +-0.933 sigma
    assert width["sigma68"] == pytest.approx(0.933 * width["sigma"], rel=0.03)
    assert width["events"] == 24000
    assert 0.9 * 20000 < width["window_events"] < 20000


def test_first_window_with_too_few_values_is_an_error() -> None:
    values = np.random.default_rng(3).normal(0.0, 1.0, 100)
    inside = int(np.sum((values >= 1.5) & (values <= 4.0)))
    with pytest.raises(ValueError, match=f"{inside} of 100 values .* fewer than 20"):
        core_width(values, window=(1.5, 4.0))


def test_no_values_is_an_error_that_says_so() -> None:
    with pytest.raises(ValueError, match="^0 values, fewer than 20$"):
        core_width(np.empty(0))
