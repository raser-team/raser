"""The electronics stage of one job: from its currents file to its waveforms file."""

import dataclasses
import math
import os

import numpy as np

from raser.core.current.currents import read_currents

from .cable import through_cable
from .spectral_noise import noise_from_spectrum
from .spice import output_noise_spectrum
from .spice import solve
from .waveforms import EventWaveforms
from .waveforms import append_waveforms

# the noise of the circuit is taken from here up to half the sampling
# frequency of the waveforms; what is slower is not in them
LOWEST_NOISE_HZ = 1e3


# an output whose largest swing is less than this of the largest of its
# event is not stored; and a part of the circuit is wide enough when
# widening it moves no stored output by as much as this of that largest
PART_EDGE = 1e-3


def _solve(chain, currents, event, circuit, cable=None):
    """The voltages of the outputs of a circuit for an event, by the names
    of the outputs; the electrodes of the circuit are some of the currents.
    The cable is that of spice.solve."""
    row_of = {name: k for k, name in enumerate(currents.electrodes)}
    electrodes = list(circuit.sources)
    solved = solve(
        chain,
        electrodes,
        currents.dt,
        event.current[[row_of[name] for name in electrodes]],
        circuit,
        cable,
    )
    return dict(zip(circuit.outputs, solved, strict=True))


def _solve_part(chain, currents, event, part_of, hit, cable=None):
    """The voltages of the outputs of the part of the circuit around the
    electrodes `hit` that is wide enough, by their names: the part with a
    margin of one is widened, its margin doubled each time, until widening
    it moves no output that is stored by PART_EDGE of the largest one, a
    new one counting as moved from zero, or it grows no more."""
    margin = 1
    part = part_of(hit, margin)
    before = _solve(chain, currents, event, part, cable)
    while True:
        margin *= 2
        wider = part_of(hit, margin)
        if list(wider.outputs) == list(part.outputs):
            return before
        after = _solve(chain, currents, event, wider, cable)
        swing = {name: np.abs(voltage).max() for name, voltage in after.items()}
        largest = max(swing.values())
        moved = max(
            np.abs(voltage - before.get(name, 0.0)).max()
            for name, voltage in after.items()
            if swing[name] >= PART_EDGE * largest
        )
        part, before = wider, after
        if moved < PART_EDGE * largest:
            return after


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
    cable,
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
        with the device and the load: every output stored of every event
        gets its own noise, drawn from the seed, the number of the event and
        the place of the output among all outputs alone, whatever else is
        stored. The noise of two outputs has nothing in common. Spectra are
        as noise_spectra gives them.
    cable : None for a read-out without cable. Otherwise the cable.Cable
        behind the outputs, with a length for each output of the circuit. The
        window of each event is lengthened by the greatest delay of the
        outputs stored, its currents zero there, so that the pulse the
        longest cable delays is whole in it; the file counts those bins, and
        t0 stays. Each output stored has the losses of its cable applied
        (cable.through_cable) and its noise spectrum is that of the circuit
        times the modulus of the transfer factor of its cable.
    circuit_values : None, or the values the circuit is made of and where each
        is from, as device_circuit gives them: they are written to the file.
    pulse_edge : None, or the way the pulse of each output goes, as
        pulse_edge.pulse_edges gives it: it is written to the file.
    part_of : None to solve the whole circuit for every event. Otherwise a
        function that gives, for the names of the electrodes with a current
        in an event and a margin, the part of the circuit around
        them that is solved: a circuit of some of the electrodes and
        outputs, by the same names, wider with a wider margin. The part
        is widened as _solve_part says.

    Of each event only the outputs whose largest swing is at least
    PART_EDGE of the largest of the event are stored, each with its noise:
    those the event hit, its charge or the crosstalk of it. An event without
    current stores none, and no noise.
    """
    currents = read_currents(currents_path)
    if os.path.exists(waveforms_path):
        os.remove(waveforms_path)
    if noise_seed is not None:
        frequencies, densities = noise_spectra(
            chain, circuit, LOWEST_NOISE_HZ, 0.5 / currents.dt
        )
    outputs = list(circuit.outputs)
    if cable is not None:
        unknown = [name for name in outputs if name not in cable.length_m]
        if unknown:
            raise ValueError(f"The cable has no length for the outputs {unknown}")
    place = {name: k for k, name in enumerate(outputs)}

    def extra_bins(names):
        """Bins that the greatest delay of the outputs takes."""
        if cable is None:
            return 0
        delay = max((cable.delay_s(name) for name in names), default=0.0)
        return math.ceil(round(delay / currents.dt, 9))

    for event in currents.events:
        bins = event.current.shape[1]
        hit = [
            name
            for name, current in zip(currents.electrodes, event.current, strict=True)
            if np.any(current)
        ]
        # the window is solved as long as the greatest delay of any output
        # asks, and cut to that of the outputs stored
        longer = dataclasses.replace(
            event, current=np.pad(event.current, ((0, 0), (0, extra_bins(outputs))))
        )
        if not hit:
            solved = {}
        elif part_of is None:
            solved = _solve(chain, currents, longer, circuit, cable)
        else:
            solved = _solve_part(chain, currents, longer, part_of, hit, cable)
        swing = {name: np.abs(voltage).max() for name, voltage in solved.items()}
        largest = max(swing.values(), default=0.0)
        names = [
            name
            for name in outputs
            if name in solved and largest > 0 and swing[name] >= PART_EDGE * largest
        ]
        count = bins + extra_bins(names)
        voltage = np.array([solved[name][:count] for name in names]).reshape(
            len(names), count
        )
        if cable is not None:
            voltage = np.array(
                [
                    through_cable(
                        cable.component, cable.length_m[name], trace, currents.dt
                    )
                    for name, trace in zip(names, voltage)
                ]
            ).reshape(len(names), count)
        if noise_seed is not None and names:
            voltage = voltage + np.array(
                [
                    noise_from_spectrum(
                        frequencies,
                        densities[place[name]]
                        * (
                            1.0
                            if cable is None
                            else np.abs(cable.transfer(name, frequencies))
                        ),
                        count,
                        currents.dt,
                        np.random.default_rng([noise_seed, event.event, place[name]]),
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
