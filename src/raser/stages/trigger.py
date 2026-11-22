"""The trigger slice of a signal job: the trigger of the digitizer, or a
trigger device of its own over several positions."""

import os

from raser.core.trigger.coincidence import CoincidenceSettings
from raser.core.trigger.conditions import TriggerConditions
from raser.core.trigger.job import read_triggered
from raser.core.trigger.job import write_coincidence
from raser.core.trigger.job import write_triggered
from raser.stages.files import output
from raser.stages.files import plots


def _component(kwargs, kind, address):
    """The content of the component of the slot `address`, as lifecycle gives
    it in kwargs["_files"][kind]."""
    if kind not in kwargs.get("_files", {}):
        raise ValueError(f"the trigger slice needs the component {address}")
    return kwargs["_files"][kind]


def triggered(kwargs, position=None):
    """The events the trigger of the digitizer component of the slot
    digitizer.device records, as the "trigger" object of the component
    (kwargs["_files"]["digitizer"]) sets it: trigger.h5
    (event numbers and trigger times [s]) and the picture trigger_amplitude in
    plots/ of its node. Returns {"events": the number of events recorded}.

    With a position, the slice trigger.<position> on the file of
    digitizer.<position>; a position that left no digitized waveforms leaves
    no file and {"events": 0}.

    A component without a "trigger" object is a ValueError."""
    upstream = "digitizer" if position is None else f"digitizer.{position}"
    name = "trigger" if position is None else f"trigger.{position}"
    if position is not None and not os.path.exists(output(kwargs, upstream)):
        return {"events": 0}
    values = _component(kwargs, "digitizer", "digitizer.device")
    if "trigger" not in values:
        raise ValueError("the component digitizer.device has no trigger")
    conditions = TriggerConditions.from_component(values["trigger"])
    write_triggered(
        output(kwargs, upstream), output(kwargs, name), conditions, plots(kwargs, name)
    )
    return {"events": int(read_triggered(output(kwargs, name)).event.size)}


def coincident(kwargs, positions):
    """The events a trigger device of its own, the component of the slot
    trigger.device (kwargs["_files"]["trigger"]), records over the positions (a list of names), each a slot of the device:
    trigger.<position>.h5 for each position, all holding the same events and
    trigger times [s], and the picture trigger_amplitude in plots/ of the
    node "trigger". Returns {"events": the number of events recorded}.

    A position that left no digitized waveforms has no file to read: its slot
    is hit in no event."""
    positions = list(positions)
    values = _component(kwargs, "trigger", "trigger.device")
    settings = CoincidenceSettings.from_component(values, positions)
    inputs = {}
    for position in positions:
        path = output(kwargs, f"digitizer.{position}")
        inputs[position] = path if os.path.exists(path) else None
    outputs = {
        position: output(kwargs, f"trigger.{position}") for position in positions
    }
    write_coincidence(inputs, outputs, settings, plots(kwargs, "trigger"))
    return {"events": int(read_triggered(outputs[positions[0]]).event.size)}
