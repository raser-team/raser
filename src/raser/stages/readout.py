"""The waveforms slice of a signal job."""

from raser.core.current.cal_current import electrode_names
from raser.core.device import build_device as bdv
from raser.core.readout.circuit import named_chain
from raser.core.field.circuit_parameters import device_sensor
from raser.core.readout.job import write_waveforms
from raser.stages.files import output


def waveforms(kwargs):
    """The currents through the sensor circuit of the device and the chain the
    amplifier names: waveforms_<job>.h5. The noise of the circuit is drawn
    with the seed lifecycle gives the slice; a run without seeds has no noise."""
    my_d = bdv.Detector(kwargs["det_name"], kwargs["_files"]["device"])
    sensor, _ = device_sensor(
        my_d, electrode_names(my_d.read_out_contact, my_d.read_ele_num)
    )
    write_waveforms(
        output(kwargs, "currents"),
        output(kwargs, "waveforms"),
        named_chain(str(kwargs["amplifier"])),
        sensor,
        kwargs.get("seed"),
    )
