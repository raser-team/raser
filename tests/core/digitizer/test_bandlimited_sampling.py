import numpy as np
import pytest

from raser.core.digitizer.bandwidth import bandlimited_interpolate, filter_waveform


BINS = 1000
DT = 1e-12
# fractions of a bin, none of them a bin centre (which is fraction 0)
OFFSETS = (0.1, 0.37, 0.5, 0.83)


def _record_cosine(periods):
    """Return a cosine with ``periods`` whole periods in the record, sampled at the bin centres.

    A cosine is used because its first and last bin centre have the same value,
    so the linear trend removed before the transform is zero. Returns the
    frequency in Hz, the voltage of shape ``(1, BINS)`` and a function that
    evaluates the cosine at any time in s.
    """
    frequency = periods / (BINS * DT)

    def analytic(time):
        return np.cos(2 * np.pi * frequency * time)

    centres = (np.arange(BINS) + 0.5) * DT
    return frequency, analytic(centres)[None, :], analytic


def _fractional_times():
    bins = np.arange(100, BINS - 100, 37)
    return np.concatenate([(bins + 0.5 + fraction) * DT for fraction in OFFSETS])


# Deliberate changes that break the tests below, each in bandlimited_interpolate:
# the weights w_j of the one-sided sum all set to 1 (the interior terms count
# half), and the reference time t_c of the first bin centre replaced by t_0 = 0
# (the waveform shifts by half a bin).
def test_none_response_follows_a_record_periodic_sine_between_bin_centres():
    frequency, voltage, analytic = _record_cosine(40)
    assert frequency < 1 / (2 * DT)
    times = _fractional_times()
    actual = bandlimited_interpolate(voltage, DT, "none", None, times)[0]
    np.testing.assert_allclose(actual, analytic(times), rtol=1e-9, atol=1e-9)


def test_brickwall_passes_a_sine_below_the_bandwidth_unchanged():
    frequency, voltage, analytic = _record_cosine(40)
    bandwidth = 2 * frequency
    times = _fractional_times()
    actual = bandlimited_interpolate(voltage, DT, "brickwall", bandwidth, times)[0]
    np.testing.assert_allclose(actual, analytic(times), rtol=1e-9, atol=1e-9)


def test_brickwall_removes_a_sine_above_the_bandwidth():
    frequency, voltage, _ = _record_cosine(200)
    bandwidth = frequency / 2
    assert frequency < 1 / (2 * DT)
    times = _fractional_times()
    actual = bandlimited_interpolate(voltage, DT, "brickwall", bandwidth, times)[0]
    np.testing.assert_allclose(actual, 0.0, rtol=0, atol=1e-9)


def test_brickwall_step_has_documented_rise_time_and_overshoot():
    dt = 1e-12
    bandwidth = 1e9
    time = (np.arange(100_000) + 0.5) * dt
    step = (time > 40e-9).astype(float)[None, :]
    filtered = filter_waveform(step, dt, "brickwall", bandwidth)[0]
    rising = np.interp([0.1, 0.9], filtered, time)
    assert rising[1] - rising[0] == pytest.approx(0.446 / bandwidth, rel=0.03)
    assert filtered.max() - 1.0 == pytest.approx(0.089, rel=0.03)


def test_bandlimited_interpolation_matches_filtered_bin_centres():
    voltage = np.sin(2 * np.pi * 2e9 * (np.arange(4000) + 0.5) * 1e-12)[None, :]
    centres = (np.arange(voltage.shape[1]) + 0.5) * 1e-12
    filtered = filter_waveform(voltage, 1e-12, "brickwall", 6e9)
    interpolated = bandlimited_interpolate(voltage, 1e-12, "brickwall", 6e9, centres)
    np.testing.assert_allclose(interpolated, filtered, rtol=1e-12, atol=1e-12)
