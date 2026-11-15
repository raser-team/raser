import numpy as np
import pytest

from raser.core.metrics.reconstruction import InputWaveform
from raser.core.metrics.reconstruction import get_amplitude
from raser.core.metrics.reconstruction import get_CFD50
from raser.core.metrics.reconstruction import get_charge
from raser.core.metrics.reconstruction import get_CoG
from raser.core.metrics.reconstruction import get_ToA
from raser.core.metrics.reconstruction import get_ToT

# a negative triangle: 2 per bin up to 10 in bin 6, then down again
TRIANGLE = np.array([0.0, 0, -2, -4, -6, -8, -10, -8, -6, -4, -2, 0, 0])
T0, DT = 3.0e-9, 1.0e-9  # bin i is centred at (3.5 + i) ns


def test_quantities_of_a_negative_triangle() -> None:
    times = T0 + (np.arange(len(TRIANGLE)) + 0.5) * DT

    amplitude, peak = get_amplitude(TRIANGLE)
    assert (amplitude, peak) == (10.0, 6)
    # the last bin below 3 before the peak is bin 2, the first after it bin 10
    assert get_ToA(times, TRIANGLE, 3.0, peak) == pytest.approx(5.5e-9)
    assert get_ToT(times, TRIANGLE, 3.0, peak) == pytest.approx(8.0e-9)
    # half the peak, 5, lies midway between bin 3 (4) and bin 4 (6)
    assert get_CFD50(times, TRIANGLE, 0.5, peak) == pytest.approx(7.0e-9)
    assert get_charge(TRIANGLE) == 50.0


def test_one_electrode_event_takes_its_bins_from_t0_and_dt() -> None:
    event = InputWaveform([TRIANGLE], T0, DT, 0.0, 3.0, 5.0, 1300.0, 1300.0)

    assert event.data["amplitude"] == 10.0
    assert event.data["ToA"] == pytest.approx(5.5e-9)
    assert event.data["CFD50"] == pytest.approx(7.0e-9)


def test_event_below_the_amplitude_threshold_has_no_time() -> None:
    event = InputWaveform([TRIANGLE], T0, DT, 0.0, 3.0, 11.0, 1300.0, 1300.0)

    assert event.data["amplitude"] is None
    assert event.data["CFD50"] is None


def test_cluster_of_three_strips_weighs_the_strips_by_amplitude() -> None:
    # strips 1 and 2 carry 10 and 5; strip 0 stays below the threshold
    voltage = [0.1 * TRIANGLE, TRIANGLE, 0.5 * TRIANGLE]
    event = InputWaveform(voltage, T0, DT, 80.0, 3.0, 4.0, 80.0, 1300.0)

    assert event.data["cluster_size_amplitude"] == 2
    assert event.data["gravity_center_amplitude"] == pytest.approx((1 * 10 + 2 * 5) / 15)
    # the track is at 80 / 80 = 1 strip
    assert event.data["gravity_center_amplitude_error"] == pytest.approx(1 / 3)


def test_centre_of_gravity_weighs_the_bins_above_the_threshold() -> None:
    # 1 is below the threshold 3: only 4, 10, 6, 4 at 1.5, 2.5, 3.5, 4.5 ns count
    samples = np.array([-1.0, -4, -10, -6, -4, -1, -8])
    times = (np.arange(len(samples)) + 0.5) * 1.0e-9

    center = get_CoG(times, samples, 3.0, 2)

    assert center == pytest.approx((1.5 * 4 + 2.5 * 10 + 3.5 * 6 + 4.5 * 4) / 24 * 1.0e-9)
