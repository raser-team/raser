"""The waveforms slice of a signal job."""

import os

from raser.core.current.cal_current import electrode_names
from raser.core.device import build_device as bdv
from raser.core.readout.circuit import named_chain
from raser.core.field.circuit_parameters import device_circuit
from raser.core.field.circuit_parameters import field_circuit
from raser.core.field.circuit_parameters import device_grid
from raser.core.field.circuit_parameters import device_row
from raser.core.field.solved import solved_field
from raser.core.readout.job import write_waveforms
from raser.stages.files import output


def waveforms(kwargs, position=None):
    """The currents through the circuit of the device and the chain the
    amplifier names: readout_<job>.h5. The noise of the circuit is drawn
    with the seed lifecycle gives the slice; a run without seeds has no noise.

    A device with a resistive layer has its currents on the cells of the
    layer and is read out on the strips or the pads on it. Its sheet
    resistance is that of its file unless sheet_resistance [Ohm] is
    given; a device without a resistive layer takes none.

    Other devices take from the field at their bias the capacitances between
    strips of a row and the undepleted bulk of a planar device; the junction
    capacitance is the measured one of the device file, else that of the
    row, else, for now, the estimate of the device, until the field gives
    one at every bias.

    With a position, the slice readout.<position> on the file of
    current.<position>; a position that left no currents leaves no file and
    {"events": 0} with its mark."""
    current = "current" if position is None else f"current.{position}"
    if position is not None and not os.path.exists(output(kwargs, current)):
        return {"events": 0}
    my_d = bdv.Detector(kwargs["det_name"], kwargs["_files"]["device"])
    electrodes = electrode_names(my_d.read_out_contact, my_d.read_ele_num)
    sheet_ohm = kwargs.get("sheet_resistance")
    if "resistive_layer" in my_d.device_dict:
        build = device_grid if my_d.is_pixel else device_row
        circuit, values = build(my_d, electrodes, sheet_ohm=sheet_ohm)
    elif sheet_ohm is not None:
        raise ValueError(
            f"{my_d.det_name} has no resistive layer to give a sheet "
            f"resistance of {sheet_ohm} Ohm"
        )
    else:
        flux = my_d.irradiation_flux
        if kwargs.get("irradiation") is not None:
            flux = float(kwargs["irradiation"])
        row, undepleted = field_circuit(solved_field(my_d, my_d.voltage, flux), my_d)
        circuit, values = device_circuit(
            my_d, electrodes, row=row, solved_undepleted=undepleted
        )
    write_waveforms(
        output(kwargs, current),
        output(kwargs, "readout" if position is None else f"readout.{position}"),
        named_chain(str(kwargs["amplifier"])),
        circuit,
        kwargs.get("seed"),
        circuit_values=values,
    )
    return None
