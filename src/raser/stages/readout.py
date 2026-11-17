"""The waveforms slice of a signal job."""

import os

from raser.core.current.cal_current import electrode_names
from raser.core.device import build_device as bdv
from raser.core.readout.circuit import named_chain
from raser.core.field.circuit_parameters import device_sensor
from raser.core.readout.job import write_waveforms
from raser.stages.files import output


def waveforms(kwargs, position=None):
    """The currents through the sensor circuit of the device and the chain the
    amplifier names: readout_<job>.h5. The noise of the circuit is drawn
    with the seed lifecycle gives the slice; a run without seeds has no noise.

    With a position, the slice readout.<position> on the file of
    current.<position>; a position that left no currents leaves no file and
    {"events": 0} with its mark."""
    current = "current" if position is None else f"current.{position}"
    if position is not None and not os.path.exists(output(kwargs, current)):
        return {"events": 0}
    my_d = bdv.Detector(kwargs["det_name"], kwargs["_files"]["device"])
    sensor, values = device_sensor(
        my_d, electrode_names(my_d.read_out_contact, my_d.read_ele_num)
    )
    write_waveforms(
        output(kwargs, current),
        output(kwargs, "readout" if position is None else f"readout.{position}"),
        named_chain(str(kwargs["amplifier"])),
        sensor,
        kwargs.get("seed"),
        sensor_values=values,
    )
    return None
