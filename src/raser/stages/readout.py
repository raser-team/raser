"""The waveforms slice of a signal job."""

from raser.core.current.cal_current import electrode_names
from raser.core.device import build_device as bdv
from raser.core.readout.circuit import named_chain
from raser.core.field.circuit_parameters import device_grid
from raser.core.field.circuit_parameters import device_row
from raser.core.field.circuit_parameters import device_sensor
from raser.core.readout.job import write_waveforms
from raser.stages.files import output


def waveforms(kwargs):
    """The currents through the sensor circuit of the device and the chain the
    amplifier names: readout_<job>.h5. The noise of the circuit is drawn
    with the seed lifecycle gives the slice; a run without seeds has no noise.

    A device with a resistive layer has its currents on the cells of the
    layer and is read out on the strips or the pads on it."""
    my_d = bdv.Detector(kwargs["det_name"], kwargs["_files"]["device"])
    electrodes = electrode_names(my_d.read_out_contact, my_d.read_ele_num)
    if "resistive_layer" in my_d.device_dict:
        build = device_grid if my_d.is_pixel else device_row
        sensor, values = build(my_d, electrodes)
    else:
        sensor, values = device_sensor(my_d, electrodes)
    write_waveforms(
        output(kwargs, "current"),
        output(kwargs, "readout"),
        named_chain(str(kwargs["amplifier"])),
        sensor,
        kwargs.get("seed"),
        sensor_values=values,
    )
