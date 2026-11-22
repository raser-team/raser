"""The reconstruction slice of a job: every event of its readout as one row.

Slice:        reconstruction, writes reconstruction.h5; with several
              positions reconstruction.<position> for each trigger.<position>
Needs:        trigger (the events recorded) and digitizer (their digitized
              waveforms), trigger.<position> and digitizer.<position> with positions
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

from raser.core.digitizer.digital_waveforms import read_digitized
from raser.core.digitizer.quantize import to_volts
from raser.core.readout.waveforms import EventWaveforms
from raser.core.readout.waveforms import Waveforms
from raser.core.reconstruction.event_table import chosen_edges
from raser.core.reconstruction.event_table import event_table
from raser.core.reconstruction.event_table import write_event_table
from raser.core.trigger.job import read_triggered
from raser.stages.files import output

MILLIVOLT = 1.0e-3  # V


def recorded_waveforms(digitizer_path, trigger_path):
    """The digitized waveforms of the events the trigger recorded, their
    codes as voltages [V]: V = (code - 2^(bits-1) + 0.5) lsb_V + offset_V.
    The k-th sample of an electrode, from 0, is at its t0 + k sampling_period [s]."""
    digitized = read_digitized(digitizer_path)
    recorded = set(read_triggered(trigger_path).event.tolist())
    period = digitized.sampling_period
    events = [
        EventWaveforms(
            record.event,
            # the times of a row are those of the middles of its bins
            record.t0 - 0.5 * period,
            to_volts(record.code, digitized.bits, digitized.lsb_V, digitized.offset_V),
            list(record.electrodes),
        )
        for record in digitized.events
        if record.event in recorded
    ]
    return Waveforms(list(digitized.electrodes), period, events, list(digitized.pulse_edge), digitized.pre_window)


def tabulate(waveforms, source, path, threshold, amplitude_threshold, fractions, edge):
    """Write the table of the events of `waveforms`, read from `source`, into `path`.

    threshold, amplitude_threshold : [mV]
    edge : "rising", "falling" or None, as `chosen_edges` takes it; each
        electrode whose pulse goes the other way than a given edge is told
    """
    edges, notes = chosen_edges(edge, waveforms.pulse_edge, waveforms.electrodes)
    for note in notes:
        print(f"{source}: {note}")
    table = event_table(waveforms, threshold * MILLIVOLT, amplitude_threshold * MILLIVOLT, fractions, edges)
    write_event_table(path, table)
    return table


def reconstruct(digitizer_path, trigger_path, path, threshold, amplitude_threshold, fractions, edge):
    """Write the table of the events of one job the trigger recorded into
    `path`, as `tabulate` does of their digitized waveforms."""
    waveforms = recorded_waveforms(digitizer_path, trigger_path)
    return tabulate(waveforms, digitizer_path, path, threshold, amplitude_threshold, fractions, edge)


def run(kwargs, position=None):
    """The slice of one job: reconstruction.h5 from trigger.h5 and digitizer.h5.

    With a position, the slice reconstruction.<position> on the files of
    trigger.<position> and digitizer.<position>; a position that left no
    trigger file leaves no file and {"events": 0} with its mark."""
    suffix = "" if position is None else f".{position}"
    if position is not None and not os.path.exists(output(kwargs, f"trigger{suffix}")):
        return {"events": 0}
    reconstruct(
        output(kwargs, f"digitizer{suffix}"),
        output(kwargs, f"trigger{suffix}"),
        output(kwargs, "reconstruction" if position is None else f"reconstruction.{position}"),
        float(kwargs["threshold"]),
        float(kwargs["amplitude_threshold"]),
        tuple(float(part) for part in kwargs["fractions"]),
        kwargs.get("edge"),
    )
    return None
