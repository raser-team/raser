"""The waveforms slice of a signal job."""

import os

from raser.core.current.cal_current import electrode_names
from raser.core.device import build_device as bdv
from raser.core.readout.circuit import named_chain
from raser.core.field.circuit_parameters import device_circuit
from raser.core.field.circuit_parameters import field_circuit
from raser.core.field.circuit_parameters import part_of_row
from raser.core.field.circuit_parameters import device_grid
from raser.core.field.circuit_parameters import device_row
from raser.core.field.solved import solved_field
from raser.core.readout.job import write_waveforms
from raser.core.readout.pulse_edge import pulse_edges
from raser.stages.files import output


def waveforms(kwargs, position=None):
    """The currents through the circuit of the device and the chain the
    amplifier names: readout_<job>.h5. The noise of the circuit is drawn
    with the seed lifecycle gives the slice; a run without seeds has no noise.
    The file says which way the pulse of each output goes.

    A device with a resistive layer has its currents on the RC nodes of the
    layer and is read out on the strips or the pads on it. Its sheet
    resistance is that of its file unless sheet_resistance [Ohm] is
    given; a device without a resistive layer takes none. It takes from
    the field the capacitance of the RC nodes and the undepleted layer, as
    the other devices do.

    Other devices take from the field at their bias the capacitances between
    strips of a row and the undepleted bulk of a planar device; the junction
    capacitance is the measured one of the device file, else that of the
    row or the one the field solved at the bias, else, for now, the
    estimate of the device, until the field solves one at every bias.
    A row of strips solves, for each event, only the strips hit and those
    their charge reaches, as job.write_waveforms widens the part of the row
    part_of_row gives, and the file holds those strips of the event alone.

    With a position, the slice readout.<position> on the file of
    current.<position>; a position that left no currents leaves no file and
    {"events": 0} with its mark."""
    current = "current" if position is None else f"current.{position}"
    if position is not None and not os.path.exists(output(kwargs, current)):
        return {"events": 0}
    my_d = bdv.Detector(kwargs["det_name"], kwargs["_files"]["device"])
    electrodes = electrode_names(my_d.read_out_contact, my_d.read_ele_num)
    part_of = None
    sheet_ohm = kwargs.get("sheet_resistance")
    has_layer = "resistive_layer" in my_d.device_dict
    if not has_layer and sheet_ohm is not None:
        raise ValueError(
            f"{my_d.det_name} has no resistive layer to give a sheet "
            f"resistance of {sheet_ohm} Ohm"
        )
    flux = my_d.irradiation_flux
    if kwargs.get("irradiation_flux") is not None:
        flux = float(kwargs["irradiation_flux"])
    row, solved_f, undepleted = field_circuit(
        solved_field(my_d, my_d.voltage, flux), my_d
    )
    if has_layer:
        build = device_grid if my_d.is_pixel else device_row
        # the part of the area of the device that one RC node takes
        share = float(my_d.p_x) / float(my_d.device_dict["l_x"])
        if my_d.is_pixel:
            share *= float(my_d.p_y) / float(my_d.device_dict["l_y"])
        circuit, values = build(
            my_d,
            electrodes,
            None if solved_f is None else solved_f * share,
            sheet_ohm=sheet_ohm,
            solved_undepleted=undepleted,
        )
    else:
        circuit, values = device_circuit(
            my_d, electrodes, solved_f, row=row, solved_undepleted=undepleted
        )
        if row is not None:

            def part_of(hit, margin):
                return part_of_row(my_d, electrodes, hit, margin, solved_f, row, solved_undepleted=undepleted)

    chain = named_chain(str(kwargs["amplifier"]))
    write_waveforms(
        output(kwargs, current),
        output(kwargs, "readout" if position is None else f"readout.{position}"),
        chain,
        circuit,
        kwargs.get("seed"),
        circuit_values=values,
        pulse_edge=pulse_edges(my_d, chain, list(circuit.outputs)),
        part_of=part_of,
    )
    return None
