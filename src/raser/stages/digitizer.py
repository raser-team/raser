"""The digitized waveforms slice of a signal job."""

import os

from raser.core.digitizer.job import write_digitized
from raser.core.digitizer.settings import DigitizerSettings
from raser.stages.files import output
from raser.stages.files import plots


def digitized(kwargs, position=None):
    """The output voltages of the electronics sampled and quantized by the
    digitizer component of the slot digitizer.device, whose content lifecycle
    gives as kwargs["_files"]["digitizer"] and whose name is kwargs["device"]:
    digitizer.h5, and the pictures samples_<event> (the first kwargs["plots"]
    events) and codes in plots/ of its node. The clock phase and the aperture
    jitter are drawn from kwargs["seed"], an integer; no electrode is
    digitized as noise only.

    With a position, the slice digitizer.<position> on the file of
    readout.<position>; a position that left no readout leaves no file and
    {"events": 0} with its mark.

    A missing kwargs["device"], ["plots"] or ["seed"], or a missing content
    of the component, is a ValueError naming it."""
    for key in ("device", "plots", "seed"):
        if key not in kwargs:
            raise ValueError(
                f"the digitizer slice needs the key {key!r} in its arguments"
            )
    if "digitizer" not in kwargs.get("_files", {}):
        raise ValueError("the digitizer slice needs the component digitizer.device")
    upstream = "readout" if position is None else f"readout.{position}"
    name = "digitizer" if position is None else f"digitizer.{position}"
    if position is not None and not os.path.exists(output(kwargs, upstream)):
        return {"events": 0}
    component = str(kwargs["device"])
    values = kwargs["_files"]["digitizer"]
    settings = DigitizerSettings.from_component(component, values)
    write_digitized(
        output(kwargs, upstream),
        output(kwargs, name),
        settings,
        component,
        int(kwargs["seed"]),
        int(kwargs["plots"]),
        plots(kwargs, name),
        lambda event: [],
    )
    return None
