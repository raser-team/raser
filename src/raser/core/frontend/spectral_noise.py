"""Noise of a given spectrum on the time bins of a waveform."""

import numpy as np

# the record the noise is made on is this many times longer than the waveform,
# so that frequencies far below one over its length are in it
RECORD = 256


def band_power(frequencies_hz, density):
    """Function giving the power of the spectrum from zero to a frequency.

    frequencies_hz : increasing frequencies [Hz].
    density : one-sided amplitude spectral density at them [unit / sqrt(Hz)];
        the spectrum is zero outside the frequencies given.
    """
    frequencies_hz = np.asarray(frequencies_hz, dtype=np.float64)
    power_density = np.square(np.asarray(density, dtype=np.float64))
    steps = np.diff(frequencies_hz)
    if frequencies_hz.size < 2 or np.any(steps <= 0):
        raise ValueError("A noise spectrum needs at least two increasing frequencies")
    cumulative = np.concatenate(
        ([0.0], np.cumsum((power_density[1:] + power_density[:-1]) / 2 * steps))
    )
    return lambda frequency: np.interp(frequency, frequencies_hz, cumulative)


def noise_from_spectrum(frequencies_hz, density, bins, dt, generator):
    """One realisation of the noise on `bins` time bins of width dt [s], in
    the unit of the density.

    The noise is stationary and Gaussian. It is made on a record RECORD times
    longer than the waveform, of which the waveform is the beginning: each
    frequency of the record gets the power the spectrum has around it, and
    the constant gets the power below the lowest one, so a waveform carries
    the slow part of the noise as an offset that differs from event to event.

    generator : numpy random Generator.
    """
    record = RECORD * bins
    step_hz = 1.0 / (record * dt)
    centres = np.fft.rfftfreq(record, d=dt)
    power = band_power(frequencies_hz, density)
    # power between the edges half a step below and above each frequency
    in_band = power(centres + step_hz / 2) - power(np.maximum(centres - step_hz / 2, 0))
    # numpy's inverse transform of a one-sided spectrum X gives the variance
    # 4 <Re X^2> / record^2 at an inner frequency and <X^2> / record^2 at the
    # constant and at the highest frequency
    sigma = record * np.sqrt(in_band) / 2
    spectrum = generator.normal(0.0, sigma) + 1j * generator.normal(0.0, sigma)
    spectrum[0] = generator.normal(0.0, record * np.sqrt(in_band[0]))
    if record % 2 == 0:
        spectrum[-1] = generator.normal(0.0, record * np.sqrt(in_band[-1]))
    return np.fft.irfft(spectrum, n=record)[:bins]
