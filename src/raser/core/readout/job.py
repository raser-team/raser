"""The electronics stage of one job: from its currents file to its waveforms file."""

import os

import numpy as np

from raser.core.current.currents import read_currents

from .spectral_noise import noise_from_spectrum
from .spice import output_noise_spectrum
from .spice import solve
from .waveforms import EventWaveforms
from .waveforms import append_waveforms

# the noise of the circuit is taken from here up to half the sampling
# frequency of the waveforms; what is slower is not in them
LOWEST_NOISE_HZ = 1e3


def write_waveforms(
    currents_path, waveforms_path, chain, sensor, noise_seed, sensor_values=None
):
    """Solve the chain for every event of the currents file and write the
    output voltages to the waveforms file, event by event.

    chain and sensor are those of spice.solve; the electrodes of the
    currents, the bin width and the time bins of each event are those of the
    currents file, the waveforms are those of the outputs of the sensor. A
    waveforms file an earlier start of the job left is replaced.

    noise_seed : None for waveforms without noise. Otherwise the seed of the
        noise of the circuit, which ngspice calculates once for the chain
        with the sensor and the load: every output of every event gets its
        own noise, in one sequence that the seed fixes. The noise of two
        outputs has nothing in common.
    sensor_values : None, or the values the sensor is made of and where each
        is from, as device_sensor gives them: they are written to the file.
    """
    currents = read_currents(currents_path)
    if os.path.exists(waveforms_path):
        os.remove(waveforms_path)
    if noise_seed is not None:
        generator = np.random.default_rng(noise_seed)
        frequencies, densities = output_noise_spectrum(
            chain, sensor, LOWEST_NOISE_HZ, 0.5 / currents.dt
        )
    for event in currents.events:
        voltage = solve(chain, currents.electrodes, currents.dt, event.current, sensor)
        if noise_seed is not None:
            voltage = voltage + np.array(
                [
                    noise_from_spectrum(
                        frequencies, density, voltage.shape[1], currents.dt, generator
                    )
                    for density in densities
                ]
            )
        append_waveforms(
            waveforms_path,
            list(sensor.outputs),
            currents.dt,
            EventWaveforms(event.event, event.t0, voltage),
            sensor_values,
        )
