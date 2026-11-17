"""The reconstruction slice of a job: every event of its readout as one row.

Slice:        reconstruction, writes reconstruction_<job>.h5; with several
              positions reconstruction.<position> for each readout.<position>
Needs:        readout (the waveforms), readout.<position> with positions
Options:      threshold            50 mV, of the times and the area
              amplitude_threshold  100 mV, of the selected events
              fractions            0.1, 0.2, ..., 0.9, of the constant-fraction times
              edge                 the edge of the pulses the thresholds are set on,
                                   as on a scope, rising or falling; not given, the
                                   edge the readout wrote its pulses with
Component files: none
Random numbers:  none
The content of the file is in raser.core.reconstruction.event_table.
"""

import os

from raser.core.readout.waveforms import read_waveforms
from raser.core.reconstruction.event_table import event_table
from raser.core.reconstruction.event_table import write_event_table
from raser.stages.files import output

MILLIVOLT = 1.0e-3  # V
DEFAULTS = {
    "threshold": 50.0,
    "amplitude_threshold": 100.0,
    "fractions": (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9),
    "edge": None,
}


def reconstruct(readout_path, path, threshold, amplitude_threshold, fractions, edge):
    """Write the table of the events of one job into `path`.

    threshold, amplitude_threshold : [mV]
    """
    waveforms = read_waveforms(readout_path)
    if edge is None:
        edges = set(waveforms.pulse_edge)
        if len(edges) != 1:
            ways = ", ".join(f"{name} {way}" for name, way in zip(waveforms.electrodes, waveforms.pulse_edge))
            raise ValueError(f"{readout_path}: the pulses go both ways ({ways}); give the edge to set the thresholds on")
        (edge,) = edges
    table = event_table(waveforms, threshold * MILLIVOLT, amplitude_threshold * MILLIVOLT, fractions, edge)
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
