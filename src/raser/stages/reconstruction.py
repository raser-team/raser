"""The reconstruction slice of a job: every event of its readout as one row.

Slice:        reconstruction, writes reconstruction_<job>.h5
Needs:        readout (the waveforms); deposit and current for the truth of
              each event (time of its earliest deposit, pairs, net charge)
Options:      threshold            50 mV, of the times and the charge
              amplitude_threshold  100 mV, of the selected events
              fractions            0.1, 0.2, ..., 0.9, of the constant-fraction times
              edge                 falling, the edge of the pulses the thresholds
                                   are set on, as on a scope: rising or falling
Component files: none
Random numbers:  none
The content of the file is in raser.core.reconstruction.event_table.
"""

from raser.core.current.currents import read_currents
from raser.core.deposit.deposits import read_deposits
from raser.core.readout.waveforms import read_waveforms
from raser.core.reconstruction.event_table import event_table
from raser.core.reconstruction.event_table import write_event_table
from raser.stages.files import output

MILLIVOLT = 1.0e-3  # V
DEFAULTS = {
    "threshold": 50.0,
    "amplitude_threshold": 100.0,
    "fractions": (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9),
    "edge": "falling",
}


def job_truth(deposit_path, current_path):
    """Geant4 event number -> (time of its earliest deposit [s], pairs it gave
    to the current, signed net charge of each electrode [C]) of a job."""
    earliest = {event.event: min(event.t) for event in read_deposits(str(deposit_path)).events}
    truth = {}
    for event in read_currents(current_path).events:
        if event.event not in earliest:
            raise ValueError(f"{current_path}: event {event.event} is not among the deposits of the job")
        truth[event.event] = (earliest[event.event], float(event.pairs), [float(value) for value in event.charge])
    return truth


def job_table(waveforms, deposit_path, current_path, threshold, amplitude_threshold, fractions, edge):
    """The table of the events of one job, from its readout as
    `read_waveforms` gives it.

    threshold, amplitude_threshold : [V]
    edge : "rising" or "falling"
    """
    return event_table(
        waveforms,
        job_truth(deposit_path, current_path),
        threshold,
        amplitude_threshold,
        fractions,
        edge,
    )


def reconstruct(readout_path, deposit_path, current_path, path, threshold, amplitude_threshold, fractions, edge):
    """Write the table of the events of one job into `path`.

    threshold, amplitude_threshold : [mV]
    """
    table = job_table(
        read_waveforms(readout_path), deposit_path, current_path,
        threshold * MILLIVOLT, amplitude_threshold * MILLIVOLT, fractions, edge,
    )
    write_event_table(path, table)
    return table


def run(kwargs, slot=None):
    """The slice of one job. `slot` names the device of the experiment the
    slice reconstructs; None for the one device of an experiment with one."""
    if slot is not None:
        raise NotImplementedError(f"slot {slot!r}: the files of a slot are not named yet")
    reconstruct(
        output(kwargs, "readout"),
        output(kwargs, "deposit"),
        output(kwargs, "current"),
        output(kwargs, "reconstruction"),
        float(kwargs["threshold"]),
        float(kwargs["amplitude_threshold"]),
        tuple(float(part) for part in kwargs["fractions"]),
        str(kwargs["edge"]),
    )
