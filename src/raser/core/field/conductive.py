"""Which part of a biased device answers a signal as a conductor.

For the weighting field the device is split in two at each bias: what conducts
is taken into the electrodes, the rest is dielectric.
"""

import numpy as np

ELEMENTARY_CHARGE = 1.602176634e-19  # C
RESISTIVITY = 10.0  # Ohm cm, below which a node is conductive
UNDEPLETED = 0.5  # carriers per net dopant, above which a doped node is not depleted


def conductive(electrons, holes, net_doping, mu_n, mu_p):
    """Whether each node is conductive, as an array of bool.

    `electrons`, `holes` and `net_doping` are in cm^-3 at the nodes of the
    solved field, the mobilities `mu_n` and `mu_p` in cm^2/(V s). A node is
    conductive when its resistivity 1 / (q (mu_n n + mu_p p)) is below
    RESISTIVITY, or when it is doped and not depleted: its carriers are more
    than UNDEPLETED of its net doping. A node without net doping is judged by
    its resistivity alone.
    """
    electrons = np.asarray(electrons, dtype=float)
    holes = np.asarray(holes, dtype=float)
    doped = np.abs(np.asarray(net_doping, dtype=float))
    conductivity = ELEMENTARY_CHARGE * (mu_n * electrons + mu_p * holes)
    low_resistivity = conductivity * RESISTIVITY > 1.0
    undepleted = (doped > 0) & (electrons + holes > UNDEPLETED * doped)
    return low_resistivity | undepleted


def undepleted_bulk(depth, electrons, holes, net_doping, mu_n, mu_p):
    """The bulk of a planar device that is not depleted, along its depth: its
    width in cm and its resistance times its area in Ohm cm^2.

    `depth` is in cm at the nodes, the rest as for `conductive`. A node is of
    the undepleted bulk when it is doped and not depleted and its resistivity
    is not below RESISTIVITY: the heavily doped layers under the electrodes
    are not of it. An interval between two such nodes is of the bulk, with
    the mean of their resistivities. A fully depleted device has no such
    interval: both values are 0.
    """
    order = np.argsort(np.asarray(depth, dtype=float))
    depth = np.asarray(depth, dtype=float)[order]
    electrons = np.asarray(electrons, dtype=float)[order]
    holes = np.asarray(holes, dtype=float)[order]
    doped = np.abs(np.asarray(net_doping, dtype=float))[order]
    conductivity = ELEMENTARY_CHARGE * (mu_n * electrons + mu_p * holes)
    of_bulk = (doped > 0) & (electrons + holes > UNDEPLETED * doped) & (conductivity * RESISTIVITY <= 1.0)
    between = of_bulk[:-1] & of_bulk[1:]
    width = np.diff(depth)[between]
    resistivity = np.zeros(len(depth))
    resistivity[of_bulk] = 1.0 / conductivity[of_bulk]
    mean = 0.5 * (resistivity[:-1] + resistivity[1:])[between]
    return float(width.sum()), float((width * mean).sum())
