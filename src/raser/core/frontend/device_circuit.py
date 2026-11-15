"""Circuit of a sensor and its values, taken from its device and its field."""

from .planar_sensor import planar_sensor
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


def device_sensor(my_d, electrodes, solved_f=None):
    """SensorCircuit of the read-out electrodes of a device, and the values it
    is made of, for the record of the run.

    electrodes : names of the read-out electrodes, those of the currents.
    solved_f : as junction_capacitance takes it.

    Every electrode has the junction capacitance to the back, on ground, and
    is read out itself. The record says what the circuit does not have: no
    capacitance between the electrodes, no undepleted layer.
    """
    farad, source = junction_capacitance(my_d, solved_f)
    sensor = side_by_side([planar_sensor(electrode, farad) for electrode in electrodes])
    values = {
        "junction_capacitance": {"farad": farad, "from": source},
        "between_electrodes": None,
        "undepleted_layer": None,
    }
    return sensor, values
