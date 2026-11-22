"""Response of the network of a resistive layer to an impulse on a point of
the device."""

import numpy as np

from .spice import solve


def _along(here_um, length_um, pitch_um, count, axis):
    """Parts of a charge at here_um that go to the cells of one axis, by the
    number of the cell: `count` cells at pitch_um, centred on length_um."""
    first_edge = (length_um - count * pitch_um) / 2
    last_edge = first_edge + count * pitch_um
    if not first_edge <= here_um <= last_edge:
        raise ValueError(
            f"The point lies at {axis} = {here_um} um, and the cells of the "
            f"layer reach from {first_edge} to {last_edge} um"
        )
    # in cell widths, from the middle of the first cell
    place = (here_um - first_edge) / pitch_um - 0.5
    if place <= 0:
        return {0: 1.0}
    if place >= count - 1:
        return {count - 1: 1.0}
    number = int(np.floor(place))
    to_next = place - number
    if to_next == 0:
        return {number: 1.0}
    return {number: 1 - to_next, number + 1: to_next}


def shares(my_d, point_um):
    """Parts of a charge on the point (x, y) [um] that go to the cells of the
    resistive layer of the device.

    my_d : the Detector. Its electrodes are the cells: x_ele_num of them at
        p_x along x and y_ele_num at p_y along y, centred on the device.
    point_um : x and y [um], 0 <= x <= l_x and 0 <= y <= l_y; x alone for a
        point on the middle line, y = l_y / 2.

    Returns the parts, which add up to 1, by the number of the cell,
    i * y_ele_num + j for the cell number i along x and j along y, from 0, as
    electrode_names orders them. Along each axis a point between the middles
    of two cells is shared between them linearly, the nearer one taking more;
    one beyond the middle of the outermost cell goes to that cell alone. The
    parts of the two axes are multiplied. A cell that takes nothing is left
    out. A point off the cells raises ValueError.
    """
    point = np.atleast_1d(np.asarray(point_um, dtype=np.float64))
    x_um = float(point[0])
    y_um = float(point[1]) if len(point) > 1 else float(my_d.l_y) / 2
    along_x = _along(x_um, float(my_d.l_x), float(my_d.p_x), int(my_d.x_ele_num), "x")
    along_y = _along(y_um, float(my_d.l_y), float(my_d.p_y), int(my_d.y_ele_num), "y")
    return {
        i * int(my_d.y_ele_num) + j: part_x * part_y
        for i, part_x in along_x.items()
        for j, part_y in along_y.items()
    }


def impulse_response(
    my_d, circuit, chain, points_um, dt=10e-12, bins=2000, charge=1e-15
):
    """Output voltages [V] of the read-outs of a device with a resistive
    layer for a charge injected at each of several points, shape
    (points, outputs, bins), the outputs in the order of circuit.outputs.

    my_d : the Detector, whose electrodes are the cells of the layer.
    circuit : DeviceCircuit of the device, its sources those of the cells.
    chain : the amplifier chain, as named_chain gives it.
    points_um : the points, each as shares takes it.
    dt : width of a time bin [s].
    bins : number of time bins.
    charge : the charge [C], injected as a rectangular current pulse in the
        first bin, shared among the cells as shares gives it.
    """
    cells = list(circuit.sources)
    count = int(my_d.x_ele_num) * int(my_d.y_ele_num)
    if len(cells) != count:
        raise ValueError(
            f"The circuit has the currents of {len(cells)} cells, and "
            f"{my_d.det_name} has {count}"
        )
    voltages = []
    for point_um in points_um:
        currents = np.zeros((count, bins))
        for number, part in shares(my_d, point_um).items():
            currents[number, 0] = part * charge / dt
        voltages.append(solve(chain, cells, dt, currents, circuit))
    return np.array(voltages)
