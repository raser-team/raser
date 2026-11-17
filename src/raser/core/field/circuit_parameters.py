"""Circuit of a device and its values, taken from its device and its field."""

import dataclasses

from . import implanted_aluminium
from .resistive_layer import resistive_grid
from .resistive_layer import resistive_row
from .device_circuit import planar_circuit
from .device_circuit import row_of_electrodes
from .device_circuit import side_by_side

VACUUM_PERMITTIVITY_F_M = 8.8541878128e-12


def junction_capacitance(my_d, solved_f=None):
    """Capacitance [F] of the depleted layer under one read-out electrode, and
    where it is from, for the record of the run:

    "device file" : capacitance_pF of the device file, a measured value;
    "field" : solved_f, the capacitance [F] the field gives at the bias of the
        run, taken when the device file has none;
    "parallel plate" : the estimate of the device from its read-out area and
        its thickness, taken when there is neither.
    """
    if "capacitance_pF" in my_d.device_dict:
        return float(my_d.device_dict["capacitance_pF"]) * 1e-12, "device file"
    if solved_f is not None:
        return float(solved_f), "field"
    estimate_pf = my_d.capacitance
    if estimate_pf is None:
        raise ValueError(
            f"{my_d.det_name} has no capacitance: its device file gives none, "
            "its field was not asked for one, and the device has no estimate"
        )
    return float(estimate_pf) * 1e-12, "parallel plate"


def bias_and_coupling(my_d):
    """Bias resistance [Ohm] and coupling capacitance [F] the device file
    gives for one read-out electrode, bias_resistance_ohm and
    coupling_capacitance_pF. None for one the device does not have: its
    electrodes are then biased, or read out, directly."""
    bias_ohm = my_d.device_dict.get("bias_resistance_ohm")
    coupling_pf = my_d.device_dict.get("coupling_capacitance_pF")
    return (
        None if bias_ohm is None else float(bias_ohm),
        None if coupling_pf is None else float(coupling_pf) * 1e-12,
    )


def undepleted_layer(
    area_m2, thickness_m, depleted_width_m, permittivity_f_per_m, resistivity_ohm_m
):
    """Resistance [Ohm] and capacitance [F] of the layer the bias does not
    deplete: a slab of the bulk between the depleted layer and the back.

    W. Riegler, NIM A 940 (2019) 453, arXiv:1812.07570, eq. 50.
    """
    if not 0 < depleted_width_m < thickness_m:
        raise ValueError(
            f"A depleted width of {depleted_width_m} m leaves no undepleted "
            f"layer in a device {thickness_m} m thick"
        )
    undepleted_m = thickness_m - depleted_width_m
    resistance_ohm = resistivity_ohm_m * undepleted_m / area_m2
    capacitance_f = permittivity_f_per_m * area_m2 / undepleted_m
    return resistance_ohm, capacitance_f


def undepleted_layer_of(my_d, solved=None):
    """Resistance [Ohm] and capacitance [F] of the layer the bias does not
    deplete, under one read-out electrode, and where they are from, for the
    record of the run. None and None for a fully depleted device.

    "device file" : undepleted_resistance_ohm and undepleted_capacitance_pF
        of the device file;
    "field" : solved, the two the field gives at the bias of the run, taken
        when the device file has neither.
    """
    keys = ("undepleted_resistance_ohm", "undepleted_capacitance_pF")
    given = [key for key in keys if key in my_d.device_dict]
    if len(given) == 1:
        raise ValueError(
            f"{my_d.det_name} gives {given[0]} alone: the undepleted layer "
            f"has both {keys[0]} and {keys[1]}"
        )
    if given:
        return (
            float(my_d.device_dict[keys[0]]),
            float(my_d.device_dict[keys[1]]) * 1e-12,
        ), "device file"
    if solved is not None:
        resistance_ohm, capacitance_f = solved
        return (float(resistance_ohm), float(capacitance_f)), "field"
    return None, None


def device_circuit(my_d, electrodes, solved_f=None, row=None, solved_undepleted=None):
    """DeviceCircuit of the read-out electrodes of a device, and the values it
    is made of, for the record of the run.

    electrodes : names of the read-out electrodes, those of the currents, in
        their order along the row.
    solved_f : as junction_capacitance takes it.
    row : None, or what the field stored of the capacitances of one strip of
        a row at the bias of the run, Capacitance_<bias>V.json: "total", the
        capacitance of the strip to all other electrodes, and "to", its parts,
        of which "neighbour<n>" is that to the two strips n places away
        together, all in F per cm of strip; "neighbours_coupled", the number
        of places up to which strips are coupled. It takes the place of
        solved_f.
    solved_undepleted : as undepleted_layer_of takes it.

    Without row every electrode has the junction capacitance to the back, on
    ground, and no capacitance to another. With row the strips up to
    neighbours_coupled places apart have theirs between them, and the rest of
    the capacitance of a strip is on ground: the back, the strips further
    away and those beyond the ends of the row, which are not read out.
    Without row a device that is not fully depleted has its undepleted layer
    behind the depleted one of every electrode. A row has none: the layer
    under strips is not a slab under each of them.
    Every electrode has the bias resistance and the coupling capacitance of
    the device file, as bias_and_coupling gives them. The electrodes count as alike
    for their noise: in a row the strips at its ends have the capacitance
    they lack to neighbours on ground, and the same in all.
    The record says what the circuit does not have.
    """
    bias_ohm, coupling_f = bias_and_coupling(my_d)
    undepleted, undepleted_from = undepleted_layer_of(my_d, solved_undepleted)
    if row is None:
        farad, source = junction_capacitance(my_d, solved_f)
        circuit = side_by_side(
            [
                planar_circuit(
                    electrode,
                    farad,
                    undepleted=undepleted,
                    bias_resistance_ohm=bias_ohm,
                    coupling_capacitance_f=coupling_f,
                )
                for electrode in electrodes
            ]
        )
        between = None
    else:
        if not my_d.is_strip:
            raise ValueError(
                f"{my_d.det_name} is not a row of strips: the capacitances "
                "between its electrodes are not taken from a row"
            )
        if undepleted is not None:
            raise ValueError(
                f"{my_d.det_name} is a row of strips and has an undepleted "
                f"layer, from the {undepleted_from}: the circuit of a row "
                "has none"
            )
        if row["unit"] != "F/cm":
            raise ValueError(f"The capacitances of the row are in {row['unit']}")
        # l_y is the length of the strips [um]
        length_cm = float(my_d.l_y) * 1e-4
        farad, source = junction_capacitance(my_d, float(row["total"]) * length_cm)
        between_f = [
            0.5 * float(row["to"][f"neighbour{apart}"]) * length_cm
            for apart in range(1, int(row["neighbours_coupled"]) + 1)
        ]
        circuits = []
        for place, electrode in enumerate(electrodes):
            to_others = sum(
                between_f[abs(place - other) - 1]
                for other in range(len(electrodes))
                if 0 < abs(place - other) <= len(between_f)
            )
            if not farad > to_others:
                raise ValueError(
                    f"{electrode} of {my_d.det_name} has {farad} F in all, from "
                    f"the {source}, and {to_others} F to the other strips, "
                    "from the field"
                )
            circuits.append(
                planar_circuit(
                    electrode,
                    farad - to_others,
                    bias_resistance_ohm=bias_ohm,
                    coupling_capacitance_f=coupling_f,
                )
            )
        circuit = row_of_electrodes(circuits, between_f)
        between = {"farad": between_f, "from": "field"}
    circuit = dataclasses.replace(circuit, outputs_alike=True)
    values = {
        "junction_capacitance": {"farad": farad, "from": source},
        "between_electrodes": between,
        "bias_resistance": None if bias_ohm is None else {"ohm": bias_ohm},
        "coupling_capacitance": None if coupling_f is None else {"farad": coupling_f},
        "undepleted_layer": None
        if undepleted is None
        else {"ohm": undepleted[0], "farad": undepleted[1], "from": undepleted_from},
    }
    return circuit, values


def sheet_resistance(my_d, chosen_ohm=None):
    """Resistance of a square [Ohm] of the resistive layer of a device, and
    where it is from, for the record of the run:

    "chosen" : chosen_ohm, a value the run is given in place of that of the
        device file, such as a point of a scan;
    "device file" : sheet_resistance [Ohm] of resistive_layer in the device
        file, a measured or a chosen value;
    "implanted layer" : that of the implanted aluminium, from implanted
        [cm^-2], thickness [um] and anneal [C] of resistive_layer, taken
        when the device file has no sheet_resistance.
    """
    layer = my_d.device_dict["resistive_layer"]
    if chosen_ohm is not None:
        return float(chosen_ohm), "chosen"
    if "sheet_resistance" in layer:
        return float(layer["sheet_resistance"]), "device file"
    return (
        implanted_aluminium.sheet_resistance(
            float(layer["implanted"]),
            float(layer["thickness"]) * 1e-4,
            float(layer["anneal"]),
            float(my_d.device_dict["temperature"]),
        ),
        "implanted layer",
    )


def device_row(my_d, cells, solved_f=None, sheet_ohm=None):
    """DeviceCircuit of the row of strips on the resistive layer of a device,
    and the values it is made of, for the record of the run.

    cells : names of the cells of the layer, those of the currents, each as
        wide as the pitch of the device.
    solved_f : capacitance [F] of one cell to the back, as
        junction_capacitance takes it.
    sheet_ohm : resistance of a square of the layer [Ohm] in place of that
        of the device, as sheet_resistance takes it.

    The strips are those of resistive_layer in the device file: for each its
    name with the numbers (from 0) of its first and last cell. Its grounded
    contacts are given the same way.
    """
    farad, capacitance_from = junction_capacitance(my_d, solved_f)
    ohm, resistance_from = sheet_resistance(my_d, sheet_ohm)
    width_m = float(my_d.p_x) * 1e-6
    length_m = float(my_d.l_y) * 1e-6
    strips = {
        name: tuple(span)
        for name, span in my_d.device_dict["resistive_layer"]["strips"].items()
    }
    grounded = {
        name: tuple(span)
        for name, span in my_d.device_dict["resistive_layer"]
        .get("grounded", {})
        .items()
    }
    circuit = resistive_row(
        cells, width_m, length_m, ohm, farad / (width_m * length_m), strips, grounded
    )
    values = {
        "cell_capacitance": {"farad": farad, "from": capacitance_from},
        "sheet_resistance": {"ohm": ohm, "from": resistance_from},
    }
    return circuit, values


def device_grid(my_d, cells, solved_f=None, sheet_ohm=None):
    """DeviceCircuit of the pads on the resistive layer of a device, and the
    values it is made of, for the record of the run.

    cells : names of the cells of the layer, those of the currents, x_ele_num
        by y_ele_num at the pitches of the device.
    solved_f : capacitance [F] of one cell to the back, as
        junction_capacitance takes it.
    sheet_ohm : as device_row takes it.

    The pads and the grounded contacts are those of resistive_layer in the
    device file. With coupling there, thickness [um] and permittivity of the
    dielectric under the pads, the pads are coupled through it.
    """
    layer = my_d.device_dict["resistive_layer"]
    farad, capacitance_from = junction_capacitance(my_d, solved_f)
    ohm, resistance_from = sheet_resistance(my_d, sheet_ohm)
    widths_m = (float(my_d.p_x) * 1e-6, float(my_d.p_y) * 1e-6)
    coupling = None
    if "coupling" in layer:
        coupling = (
            VACUUM_PERMITTIVITY_F_M
            * float(layer["coupling"]["permittivity"])
            / (float(layer["coupling"]["thickness"]) * 1e-6)
        )
    circuit = resistive_grid(
        cells,
        (my_d.x_ele_num, my_d.y_ele_num),
        widths_m,
        ohm,
        farad / (widths_m[0] * widths_m[1]),
        {name: tuple(span) for name, span in layer["pads"].items()},
        coupling,
        {
            name: [tuple(span) for span in spans]
            for name, spans in layer.get("grounded", {}).items()
        },
    )
    values = {
        "cell_capacitance": {"farad": farad, "from": capacitance_from},
        "sheet_resistance": {"ohm": ohm, "from": resistance_from},
        "coupling_per_area_f_m2": coupling,
    }
    return circuit, values
