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


def noise_spectra(chain, circuit, lowest_hz, highest_hz):
    """Noise spectrum of every output of the circuit, as
    spice.output_noise_spectrum gives it, shape (outputs, frequencies) in
    the order of circuit.outputs, with the frequencies: the outputs of one
    group of circuit.alike take the spectrum of the middle one of the
    group, the others their own. Each spectrum analysed takes the whole
    circuit."""
    outputs = list(circuit.outputs)
    taken = {output: output for output in outputs}
    for group in circuit.alike:
        for output in group:
            taken[output] = group[len(group) // 2]
    analysed = list(dict.fromkeys(taken[output] for output in outputs))
    frequencies, densities = output_noise_spectrum(
        chain, circuit, lowest_hz, highest_hz, analysed
    )
    return frequencies, np.array(
        [densities[analysed.index(taken[output])] for output in outputs]
    )


def write_waveforms(
    currents_path,
    waveforms_path,
    chain,
    circuit,
    noise_seed,
    circuit_values=None,
    pulse_edge=None,
):
    """Solve the chain for every event of the currents file and write the
    output voltages to the waveforms file, event by event.

    chain and circuit are those of spice.solve; the electrodes of the
    currents, the bin width and the time bins of each event are those of the
    currents file, the waveforms are those of the outputs of the circuit. A
    waveforms file an earlier start of the job left is replaced.

    noise_seed : None for waveforms without noise. Otherwise the seed of the
        noise of the circuit, which ngspice calculates once for the chain
        with the device and the load: every output of every event gets its
        own noise, in one sequence that the seed fixes. The noise of two
        outputs has nothing in common. Spectra are as noise_spectra gives
        them.
    circuit_values : None, or the values the circuit is made of and where each
        is from, as device_circuit gives them: they are written to the file.
    pulse_edge : None, or the way the pulse of each output goes, as
        pulse_edge.pulse_edges gives it: it is written to the file.
    """
    currents = read_currents(currents_path)
    if os.path.exists(waveforms_path):
        os.remove(waveforms_path)
    if noise_seed is not None:
        generator = np.random.default_rng(noise_seed)
        frequencies, densities = noise_spectra(
            chain, circuit, LOWEST_NOISE_HZ, 0.5 / currents.dt
        )
    for event in currents.events:
        voltage = solve(chain, currents.electrodes, currents.dt, event.current, circuit)
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
            list(circuit.outputs),
            currents.dt,
            EventWaveforms(event.event, event.t0, voltage),
            circuit_values,
            pulse_edge,
        )
