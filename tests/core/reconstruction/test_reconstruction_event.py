import numpy as np
import pytest

from raser.core.reconstruction.event import InputWaveform
from raser.core.reconstruction.event import get_amplitude
from raser.core.reconstruction.event import get_CFD50
from raser.core.reconstruction.event import get_charge
from raser.core.reconstruction.event import get_CoG
from raser.core.reconstruction.event import get_ToA
from raser.core.reconstruction.event import get_ToT
from raser.core.reconstruction.event import net_pulse
from raser.core.reconstruction import event_table as event_table_module
from raser.core.reconstruction.event_table import event_table
from raser.core.readout.waveforms import EventWaveforms, Waveforms

# a triangle: 2 per bin up to 10 in bin 6, then down again
TRIANGLE = np.array([0.0, 0, 2, 4, 6, 8, 10, 8, 6, 4, 2, 0, 0])
T0, DT = 3.0e-9, 1.0e-9  # bin i is centred at (3.5 + i) ns


def test_quantities_of_a_triangle() -> None:
    times = T0 + (np.arange(len(TRIANGLE)) + 0.5) * DT

    amplitude, peak = get_amplitude(TRIANGLE)
    assert (amplitude, peak) == (10.0, 6)
    # 3 lies midway between bin 2 (2) and bin 3 (4), and again between bin 9 and bin 10
    assert get_ToA(times, TRIANGLE, 3.0, peak) == pytest.approx(6.0e-9)
    assert get_ToT(times, TRIANGLE, 3.0, peak) == pytest.approx(7.0e-9)
    # half the peak, 5, lies midway between bin 3 (4) and bin 4 (6)
    assert get_CFD50(times, TRIANGLE, 0.5, peak) == pytest.approx(7.0e-9)
    assert get_charge(TRIANGLE) == 50.0


def test_threshold_near_the_peak_is_crossed_by_the_bins_next_to_it() -> None:
    # a sharp pulse: the edges are steep next to the peak and slow after,
    # so a line through bins farther from the peak lands elsewhere
    samples = np.array([0.0, 1, 2, 7, 10, 4, 3, 2, 1, 0])
    times = (np.arange(len(samples)) + 0.5) * 1.0e-9
    _, peak = get_amplitude(samples)

    # 9 is a third of the way from 10 back to 7 (bins 4 and 3), and a sixth
    # of the way from 10 down to 4 (bins 4 and 5)
    assert get_ToA(times, samples, 9.0, peak) == pytest.approx((4.5 - 1 / 3) * 1.0e-9)
    assert get_ToT(times, samples, 9.0, peak) == pytest.approx((1 / 3 + 1 / 6) * 1.0e-9)


def test_one_electrode_event_takes_its_bins_from_t0_and_dt() -> None:
    event = InputWaveform([TRIANGLE], T0, DT, 0.0, 3.0, 5.0, 1300.0, 1300.0)

    assert event.data["amplitude"] == 10.0
    assert event.data["ToA"] == pytest.approx(6.0e-9)
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
    samples = np.array([1.0, 4, 10, 6, 4, 1, 8])
    times = (np.arange(len(samples)) + 0.5) * 1.0e-9

    center = get_CoG(times, samples, 3.0, 2)

    assert center == pytest.approx((1.5 * 4 + 2.5 * 10 + 3.5 * 6 + 4.5 * 4) / 24 * 1.0e-9)


def test_samples_below_the_baseline_do_not_count_as_pulse() -> None:
    # a dip to -12 right before the edge is farther from zero than the peak
    samples = np.array([0.0, -12, 4, 6, 8, 10, 8, 6, 4, 2, 0])
    times = (np.arange(len(samples)) + 0.5) * 1.0e-9

    amplitude, peak = get_amplitude(samples)

    assert (amplitude, peak) == (10.0, 5)
    # the dip is below the threshold 3: the edge crosses it 15 / 16 of the
    # way from the dip to the 4 after it, and falls through it midway from 4 to 2
    assert get_ToA(times, samples, 3.0, peak) == pytest.approx((1.5 + 15 / 16) * 1.0e-9)
    assert get_ToT(times, samples, 3.0, peak) == pytest.approx((9.0 - 1.5 - 15 / 16) * 1.0e-9)


def test_net_pulse_is_the_samples_about_the_mean_of_the_first_ones() -> None:
    # 200 samples at 5 +- 1 before a pulse that reaches 20 below them
    before = 5.0 + np.tile([1.0, -1.0], 100)
    samples = np.concatenate([before, [5.0, -5.0, -15.0, -5.0, 5.0]])

    net, baseline, noise = net_pulse(samples, 200)

    assert (baseline, noise) == pytest.approx((5.0, 1.0))
    assert net[200:] == pytest.approx(np.array([0.0, -10.0, -20.0, -10.0, 0.0]))


def test_waveform_without_samples_after_the_baseline_is_an_error() -> None:
    with pytest.raises(ValueError, match="200 samples, not more than the 200"):
        net_pulse(np.zeros(200), 200)


def _table(samples, dt, pre_window):
    waveforms = Waveforms(
        ["a"],
        dt,
        [EventWaveforms(0, 0.0, np.array([samples]), ["a"])],
        ["rising"],
        pre_window,
    )
    return event_table(waveforms, 0.5, 0.5, (0.5,), ["rising"])


def test_baseline_is_taken_from_the_part_before_the_pulse_only() -> None:
    # 50 bins of 1 ns at 0.25, then a pulse a thousand times larger
    samples = np.concatenate([np.full(50, 0.25), 1000.0 * TRIANGLE])

    table = _table(samples, 1.0e-9, 50.0e-9)

    assert table.columns["baseline"][0, 0] == 0.25
    assert table.columns["noise"][0, 0] == 0.0


@pytest.mark.parametrize(
    "pre_window, bins", [(15.0e-9, 240), (240 * 62.5e-12 - 31.25e-12, 239)]
)
def test_baseline_holds_the_whole_bins_of_the_part_before_the_pulse(
    monkeypatch, pre_window, bins
) -> None:
    taken = []

    def counted(samples, baseline_points):
        taken.append(baseline_points)
        return net_pulse(samples, baseline_points)

    monkeypatch.setattr(event_table_module, "net_pulse", counted)

    _table(np.zeros(300), 62.5e-12, pre_window)

    # 15 ns is exactly 240 bins of 62.5 ps; half a bin less is 239 whole ones
    assert taken == [bins]


def test_part_before_the_pulse_of_one_bin_is_an_error() -> None:
    with pytest.raises(ValueError) as error:
        _table(np.zeros(20), 1.0e-9, 1.5e-9)

    assert str(error.value) == (
        "the baseline before the pulse holds 1 samples of 1e-09 s in "
        "pre_window 1.5e-09 s: lengthen readout.pre_window_ns"
    )
