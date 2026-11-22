"""Response of the network of a resistive layer to an impulse on a point of
the device."""

import numpy as np

from raser.core.field.resistive_layer import shares

from .spice import solve


def impulse_response(
    my_d, circuit, chain, points_um, dt=10e-12, bins=2000, charge=1e-15
):
    """Output voltages [V] of the read-outs of a device with a resistive
    layer for a charge injected at each of several points, shape
    (points, outputs, bins), the outputs in the order of circuit.outputs.

    my_d : the Detector, whose electrodes are the RC nodes of the layer.
    circuit : DeviceCircuit of the device, its sources those of the RC nodes.
    chain : the amplifier chain, as named_chain gives it.
    points_um : the points, each as shares takes it.
    dt : width of a time bin [s].
    bins : number of time bins.
    charge : the charge [C], injected as a rectangular current pulse in the
        first bin, shared among the RC nodes as shares gives it.
    """
    rc_nodes = list(circuit.sources)
    count = int(my_d.x_ele_num) * int(my_d.y_ele_num)
    if len(rc_nodes) != count:
        raise ValueError(
            f"The circuit has the currents of {len(rc_nodes)} RC nodes, and "
            f"{my_d.det_name} has {count}"
        )
    voltages = []
    for point_um in points_um:
        currents = np.zeros((count, bins))
        for number, part in shares(my_d, point_um).items():
            currents[number, 0] = part * charge / dt
        voltages.append(solve(chain, rc_nodes, dt, currents, circuit))
    return np.array(voltages)
