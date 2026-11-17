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


# the outputs at the ends of a part of the circuit hold less than this of
# its largest output, or the part grows
PART_EDGE = 1e-3


def _solve_part(chain, currents, event, part_of):
    """The outputs of the part of the circuit part_of gives for the
    electrodes of an event with a current, as wide as write_waveforms says,
    and their voltages, shape (outputs of the part, bins): none for an event
    without current."""
    hit = [k for k, current in enumerate(event.current) if np.any(current)]
    if not hit:
        return [], np.zeros((0, event.current.shape[1]))
    row_of = {name: k for k, name in enumerate(currents.electrodes)}
    margin, before = 1, None
    while True:
        part = part_of(hit, margin)
        electrodes = list(part.sources)
        solved = solve(
            chain,
            electrodes,
            currents.dt,
            event.current[[row_of[name] for name in electrodes]],
            part,
        )
        peaks = np.abs(solved).max(axis=1)
        if electrodes == before or max(peaks[0], peaks[-1]) < PART_EDGE * peaks.max():
            break
        margin, before = 2 * margin, electrodes
    return list(part.outputs), solved


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
    part_of=None,
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
    part_of : None to solve the whole circuit for every event. Otherwise a
        function that gives, for the numbers of the electrodes with a
        current in an event and a margin, the part of the circuit around
        them that is solved: a circuit of some of the electrodes and
        outputs, by the same names, wider with a wider margin. The part
        grows until its outputs at both ends hold less than PART_EDGE of the
        largest output, or it grows no more. Only its outputs are written
        for the event, each with its noise; the outputs outside it are not
        there, and an event without current has no waveforms.
    """
    currents = read_currents(currents_path)
    if os.path.exists(waveforms_path):
        os.remove(waveforms_path)
    if noise_seed is not None:
        generator = np.random.default_rng(noise_seed)
        frequencies, densities = noise_spectra(
            chain, circuit, LOWEST_NOISE_HZ, 0.5 / currents.dt
        )
    outputs = list(circuit.outputs)
    place = {name: k for k, name in enumerate(outputs)}
    for event in currents.events:
        if part_of is None:
            names = outputs
            voltage = solve(
                chain, currents.electrodes, currents.dt, event.current, circuit
            )
        else:
            names, voltage = _solve_part(chain, currents, event, part_of)
        if noise_seed is not None and names:
            voltage = voltage + np.array(
                [
                    noise_from_spectrum(
                        frequencies,
                        densities[place[name]],
                        voltage.shape[1],
                        currents.dt,
                        generator,
                    )
                    for name in names
                ]
            )
        append_waveforms(
            waveforms_path,
            outputs,
            currents.dt,
            EventWaveforms(event.event, event.t0, voltage, names),
            circuit_values,
            pulse_edge,
        )
