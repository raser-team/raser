"""The reconstruction slice of a job: every event of its readout as one row.

Slice:        reconstruction, writes reconstruction_<job>.h5; with several
              positions reconstruction.<position> for each readout.<position>
Needs:        readout (the waveforms), readout.<position> with positions
Options:      (their defaults are declared with the chain, in raser.stages.chain)
              threshold            of the times and the area [mV]
              amplitude_threshold  of the selected events [mV]
              fractions            of the constant-fraction times
              edge                 the edge of the pulses the thresholds are set on,
                                   as on a scope, rising or falling; not given, for
                                   each electrode the edge the readout wrote its
                                   pulses with; given, each electrode whose pulse
                                   goes the other way is told
Component files: none
Random numbers:  none
The content of the file is in raser.core.reconstruction.event_table.
"""

import os

from raser.core.readout.waveforms import read_waveforms
from raser.core.reconstruction.event_table import chosen_edges
from raser.core.reconstruction.event_table import event_table
from raser.core.reconstruction.event_table import write_event_table
from raser.stages.files import output

MILLIVOLT = 1.0e-3  # V


def reconstruct(readout_path, path, threshold, amplitude_threshold, fractions, edge):
    """Write the table of the events of one job into `path`.

    threshold, amplitude_threshold : [mV]
    edge : "rising", "falling" or None, as `chosen_edges` takes it; each
        electrode whose pulse goes the other way than a given edge is told
    """
    waveforms = read_waveforms(readout_path)
    edges, notes = chosen_edges(edge, waveforms.pulse_edge, waveforms.electrodes)
    for note in notes:
        print(f"{readout_path}: {note}")
    table = event_table(waveforms, threshold * MILLIVOLT, amplitude_threshold * MILLIVOLT, fractions, edges)
    write_event_table(path, table)
    return table


def run(kwargs, position=None):
    """The slice of one job: reconstruction_<job>.h5 from readout_<job>.h5.

    With a position, the slice reconstruction.<position> on the file of
    readout.<position>; a position that left no readout leaves no file and
    {"events": 0} with its mark."""
    readout = "readout" if position is None else f"readout.{position}"
    if position is not None and not os.path.exists(output(kwargs, readout)):
        return {"events": 0}
    reconstruct(
        output(kwargs, readout),
        output(kwargs, "reconstruction" if position is None else f"reconstruction.{position}"),
        float(kwargs["threshold"]),
        float(kwargs["amplitude_threshold"]),
        tuple(float(part) for part in kwargs["fractions"]),
        kwargs.get("edge"),
    )
    return None
