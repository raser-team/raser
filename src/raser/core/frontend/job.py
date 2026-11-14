"""The electronics stage of one job: from its currents file to its waveforms file."""

import os

from raser.core.current.currents import read_currents

from .spice import solve
from .waveforms import EventWaveforms
from .waveforms import append_waveforms


def write_waveforms(currents_path, waveforms_path, chain, sensor):
    """Solve the chain for every event of the currents file and write the
    output voltages to the waveforms file, event by event.

    chain and sensor are those of spice.solve; the electrodes, the bin width
    and the time bins of each event are those of the currents file. A
    waveforms file an earlier start of the job left is replaced.
    """
    currents = read_currents(currents_path)
    if os.path.exists(waveforms_path):
        os.remove(waveforms_path)
    for event in currents.events:
        voltage = solve(chain, currents.electrodes, currents.dt, event.current, sensor)
        append_waveforms(
            waveforms_path,
            currents.electrodes,
            currents.dt,
            EventWaveforms(event.event, event.t0, voltage),
        )
