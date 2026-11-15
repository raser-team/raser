"""Circuit of a sensor and its values, taken from its device and its field."""

from .planar_sensor import planar_sensor
from .planar_sensor import row_of_electrodes
from .planar_sensor import side_by_side


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


def on_sensor(my_d):
    """Bias resistance [Ohm] and coupling capacitance [F] the device file
    gives for one read-out electrode, bias_resistance_ohm and
    coupling_capacitance_pF. None for one the sensor does not have: its
    electrodes are then biased, or read out, directly."""
    bias_ohm = my_d.device_dict.get("bias_resistance_ohm")
    coupling_pf = my_d.device_dict.get("coupling_capacitance_pF")
    return (
        None if bias_ohm is None else float(bias_ohm),
        None if coupling_pf is None else float(coupling_pf) * 1e-12,
    )


def device_sensor(my_d, electrodes, solved_f=None, row=None):
    """SensorCircuit of the read-out electrodes of a device, and the values it
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

    Without row every electrode has the junction capacitance to the back, on
    ground, and no capacitance to another. With row the strips up to
    neighbours_coupled places apart have theirs between them, and the rest of
    the capacitance of a strip is on ground: the back, the strips further
    away and those beyond the ends of the row, which are not read out.
    Every electrode has the bias resistance and the coupling capacitance of
    the device file, as on_sensor gives them.
    The record says what the circuit does not have.
    """
    bias_ohm, coupling_f = on_sensor(my_d)
    if row is None:
        farad, source = junction_capacitance(my_d, solved_f)
        sensor = side_by_side(
            [
                planar_sensor(
                    electrode,
                    farad,
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
        if row["unit"] != "F/cm":
            raise ValueError(f"The capacitances of the row are in {row['unit']}")
        # l_y is the length of the strips [um]
        length_cm = float(my_d.l_y) * 1e-4
        farad, source = junction_capacitance(my_d, float(row["total"]) * length_cm)
        between_f = [
            0.5 * float(row["to"][f"neighbour{apart}"]) * length_cm
            for apart in range(1, int(row["neighbours_coupled"]) + 1)
        ]
        sensors = []
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
            sensors.append(
                planar_sensor(
                    electrode,
                    farad - to_others,
                    bias_resistance_ohm=bias_ohm,
                    coupling_capacitance_f=coupling_f,
                )
            )
        sensor = row_of_electrodes(sensors, between_f)
        between = {"farad": between_f, "from": "field"}
    values = {
        "junction_capacitance": {"farad": farad, "from": source},
        "between_electrodes": between,
        "bias_resistance": None if bias_ohm is None else {"ohm": bias_ohm},
        "coupling_capacitance": None if coupling_f is None else {"farad": coupling_f},
        "undepleted_layer": None,
    }
    return sensor, values
