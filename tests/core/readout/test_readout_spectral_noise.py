import numpy as np
import pytest

from raser.core.readout.spectral_noise import noise_from_spectrum

DT_S = 1e-11
BINS = 200  # a 2 ns waveform


def _events(frequencies_hz, density, count):
    generator = np.random.default_rng(7)
    return np.array(
        [
            noise_from_spectrum(frequencies_hz, density, BINS, DT_S, generator)
            for _ in range(count)
        ]
    )


def test_white_spectrum_gives_its_rms():
    # 1e-5 / sqrt(Hz) up to the highest frequency of the bins, 50 GHz
    highest_hz = 0.5 / DT_S
    events = _events([0.0, highest_hz], [1e-5, 1e-5], 400)

    assert events.std() == pytest.approx(1e-5 * np.sqrt(highest_hz), rel=0.02)
    # white noise: neighbouring bins have nothing to do with one another
    neighbours = np.mean(events[:, 1:] * events[:, :-1]) / events.var()
    assert abs(neighbours) < 0.02


def test_noise_slower_than_the_waveform_is_an_offset_of_each_event():
    # 1e-3 / sqrt(Hz) between 10 and 100 kHz: a period is five thousand
    # waveforms and more, longer than the record the noise is made on
    events = _events([1e4, 1e5], [1e-3, 1e-3], 2000)

    rms = 1e-3 * np.sqrt(9e4)
    assert events.mean(axis=1).std() == pytest.approx(rms, rel=0.05)
    # within one waveform it does not move
    assert np.median(events.std(axis=1)) < 0.01 * rms


def test_noise_does_not_repeat_with_the_length_of_the_waveform():
    # 1e-5 / sqrt(Hz) between 0.3 and 0.7 GHz, around one over the 2 ns of the
    # waveform: its two ends, 1.99 ns apart, are correlated by
    # cos(2 pi 0.5 GHz 1.99 ns) sinc(0.4 GHz 1.99 ns) = 0.24, not by 1
    events = _events([0.3e9, 0.7e9], [1e-5, 1e-5], 2000)

    ends = np.mean(events[:, 0] * events[:, -1]) / events.var()
    assert ends == pytest.approx(0.24, abs=0.08)


def test_noise_around_one_frequency_swings_at_it():
    # 1e-5 / sqrt(Hz) between 4.5 and 5.5 GHz: ten periods in a waveform
    events = _events([4.5e9, 5.5e9], [1e-5, 1e-5], 400)

    assert events.std() == pytest.approx(1e-5 * np.sqrt(1e9), rel=0.05)
    # half a period later the noise is the opposite
    half_period = round(0.5 / 5e9 / DT_S)
    opposite = np.mean(events[:, half_period:] * events[:, :-half_period])
    assert opposite / events.var() == pytest.approx(-0.98, abs=0.05)
