import numpy as np
import pytest


pytestmark = pytest.mark.root


def test_numpy_amplifier_convolution_uses_bin_sequence():
    from raser.core.analog.readout import _convolve_samples

    values = np.array([1.0, 2.0, 0.0, 0.0], dtype=np.float64)

    def pulse_response(time):
        return 10.0 if 0.0 <= time < 2.0 else 0.0

    convolved = _convolve_samples(values, 1.0, [pulse_response])

    assert convolved == pytest.approx([10.0, 30.0, 20.0, 0.0])


def test_numpy_amplifier_convolution_rejects_bad_bin_width():
    from raser.core.analog.readout import _convolve_samples

    with pytest.raises(ValueError, match="bin width"):
        _convolve_samples(np.array([1.0]), 0.0, [])


def test_histogram_convolution_preserves_time_axis():
    import ROOT

    from raser.core.analog.readout import _convolve_histogram_causal

    source = ROOT.TH1F("source_for_causal_convolution", "", 6, -2.0, 4.0)
    source.SetBinContent(3, 1.0)

    def pulse_response(time):
        return 1.0 if 0.0 <= time < 1.0 else 0.0

    numpy_result = _convolve_histogram_causal(source, [pulse_response])

    assert numpy_result == pytest.approx([0.0, 0.0, 1.0, 0.0, 0.0, 0.0])


def test_root_signal_convolution_preserves_time_axis():
    import ROOT

    from raser.supports.math import signal_convolution

    source = ROOT.TH1F("source_for_root_causal_convolution", "", 6, -2.0, 4.0)
    target = ROOT.TH1F("target_for_root_causal_convolution", "", 6, -2.0, 4.0)
    source.SetBinContent(3, 1.0)

    def pulse_response(time):
        return 1.0 if 0.0 <= time < 1.0 else 0.0

    signal_convolution(source, target, [pulse_response])

    assert [target.GetBinContent(i) for i in range(1, 7)] == pytest.approx(
        [0.0, 0.0, 1.0, 0.0, 0.0, 0.0]
    )


def test_signal_activity_window_ignores_full_histogram_padding():
    import ROOT

    from raser.core.analog.readout import _combined_activity_window

    current = ROOT.TH1F("current_for_activity_window", "", 100, -1e-9, 9e-9)
    electronics = ROOT.TH1F("electronics_for_activity_window", "", 100, -1e-9, 9e-9)
    current.SetBinContent(current.FindBin(0.1e-9), 10.0)
    current.SetBinContent(current.FindBin(0.3e-9), 5.0)
    electronics.SetBinContent(electronics.FindBin(0.2e-9), 20.0)
    electronics.SetBinContent(electronics.FindBin(1.0e-9), 1.0)

    xmin, xmax = _combined_activity_window(
        [current, electronics],
        absolute_thresholds=[0.0, 0.5],
    )

    assert xmin == pytest.approx(-0.5e-9)
    assert xmax == pytest.approx(2e-9)


def test_amplifier_requires_detector_capacitance():
    import ROOT

    from raser.core.analog.readout import Amplifier

    source = ROOT.TH1F("source_without_detector_capacitance", "", 4, 0.0, 4.0)

    with pytest.raises(ValueError, match="Detector capacitance"):
        Amplifier([source], "Broad_Band_UCSC")
