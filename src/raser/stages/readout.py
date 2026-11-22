"""The waveforms slice of a signal job."""

import math
import os

from raser.core.current.cal_current import electrode_names
from raser.core.current.currents import read_currents
from raser.core.device import build_device as bdv
from raser.core.readout.cable import Cable
from raser.core.readout.cable import read_cable
from raser.core.readout.circuit import named_chain
from raser.core.field.circuit_parameters import device_circuit
from raser.core.field.circuit_parameters import field_circuit
from raser.core.field.circuit_parameters import part_of_row
from raser.core.field.circuit_parameters import device_grid
from raser.core.field.circuit_parameters import device_row
from raser.core.field.solved import solved_field
from raser.core.readout.job import write_waveforms
from raser.core.readout.pulse_edge import pulse_edges
from raser.core.readout.window import post_window
from raser.stages.files import field_project
from raser.stages.files import output


def cable_of(kwargs, det_name, outputs):
    """The cable.Cable the settings give behind the outputs of the device,
    or None for a read-out without cable.

    kwargs["cable"] is None or missing for no cable; otherwise the name of a
    cable component, or an object with its "name" and "length_m", the length
    [m] of the cable of each output by the name of the output. Every output
    needs a length, a finite number of at least zero.
    """
    given = kwargs.get("cable")
    if given is None:
        return None
    if isinstance(given, str):
        given = {"name": given}
    if "name" not in given:
        raise ValueError("readout.cable needs the name of a cable component")
    lengths = given.get("length_m", {})
    for channel in outputs:
        if channel not in lengths:
            raise ValueError(
                f"readout.cable.length_m.{channel} is missing: give a cable "
                f"length in m for each output of {det_name} ({outputs})"
            )
    unknown = [channel for channel in lengths if channel not in outputs]
    if unknown:
        raise ValueError(
            f"readout.cable.length_m has unknown channels {unknown}; "
            f"the outputs of {det_name} are {outputs}"
        )
    for channel, value in lengths.items():
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value < 0
        ):
            raise ValueError(
                f"readout.cable.length_m.{channel} must be a finite "
                f"non-negative number in m, not {value}"
            )
    return Cable(
        read_cable(given["name"]),
        {channel: float(lengths[channel]) for channel in outputs},
    )


def window_lengths(kwargs):
    """The lengths [ns] of the baseline before the signal and of the longest
    settling segment after it, from readout.pre_window_ns and
    readout.max_post_window_ns. Both are needed; the first is a finite number
    of at least zero, the second a finite number above zero."""
    pre = kwargs.get("pre_window_ns")
    if pre is None:
        raise ValueError(
            "readout.pre_window_ns is missing: give the length of the baseline "
            "before the signal in ns"
        )
    longest = kwargs.get("max_post_window_ns")
    if longest is None:
        raise ValueError(
            "readout.max_post_window_ns is missing: give the longest settling "
            "segment after the signal in ns"
        )
    if isinstance(pre, bool) or not isinstance(pre, (int, float)) or not math.isfinite(pre) or pre < 0:
        raise ValueError(
            f"readout.pre_window_ns must be a finite non-negative number in ns, not {pre}"
        )
    if (
        isinstance(longest, bool)
        or not isinstance(longest, (int, float))
        or not math.isfinite(longest)
        or longest <= 0
    ):
        raise ValueError(
            f"readout.max_post_window_ns must be a positive finite number in ns, not {longest}"
        )
    return float(pre), float(longest)


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
    pre_ns, max_post_ns = window_lengths(kwargs)
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
    with field_project(kwargs):
        directory = solved_field(my_d, my_d.voltage, flux)
    row, solved_f, undepleted = field_circuit(directory, my_d)
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
    dt = read_currents(output(kwargs, current)).dt
    capacitance = values["rc_node_capacitance" if "resistive_layer" in my_d.device_dict else "junction_capacitance"]
    post_s = post_window(chain, capacitance["farad"], dt, max_post_ns * 1e-9)
    write_waveforms(
        output(kwargs, current),
        output(kwargs, "readout" if position is None else f"readout.{position}"),
        chain,
        circuit,
        kwargs.get("seed"),
        cable_of(kwargs, kwargs["det_name"], list(circuit.outputs)),
        circuit_values=values,
        pulse_edge=pulse_edges(my_d, chain, list(circuit.outputs)),
        part_of=part_of,
        pre_window_s=pre_ns * 1e-9,
        post_window_s=post_s,
    )
    return None
