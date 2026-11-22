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


def _of_undepleted_bulk(electrons, holes, net_doping, mu_n, mu_p):
    """Which nodes are of the undepleted bulk, as an array of bool, and the
    conductivity of every node [1/(Ohm cm)].

    The arguments are as for `conductive`. A node is of the undepleted bulk
    when it is doped and not depleted and its resistivity is not below
    RESISTIVITY: the heavily doped layers under the electrodes are not of it.
    """
    electrons = np.asarray(electrons, dtype=float)
    holes = np.asarray(holes, dtype=float)
    doped = np.abs(np.asarray(net_doping, dtype=float))
    conductivity = ELEMENTARY_CHARGE * (mu_n * electrons + mu_p * holes)
    of_bulk = (doped > 0) & (electrons + holes > UNDEPLETED * doped) & (conductivity * RESISTIVITY <= 1.0)
    return of_bulk, conductivity


def undepleted_bulk(depth, electrons, holes, net_doping, mu_n, mu_p):
    """The bulk of a planar device that is not depleted, along its depth: its
    width in cm and its resistance times its area in Ohm cm^2.

    `depth` is in cm at the nodes, the rest as for `conductive`. A node is of
    the undepleted bulk as `_of_undepleted_bulk` judges it. An interval
    between two such nodes is of the bulk, with the mean of their
    resistivities. A fully depleted device has no such interval: both values
    are 0.
    """
    order = np.argsort(np.asarray(depth, dtype=float))
    depth = np.asarray(depth, dtype=float)[order]
    of_bulk, conductivity = _of_undepleted_bulk(
        np.asarray(electrons, dtype=float)[order],
        np.asarray(holes, dtype=float)[order],
        np.asarray(net_doping, dtype=float)[order],
        mu_n,
        mu_p,
    )
    between = of_bulk[:-1] & of_bulk[1:]
    width = np.diff(depth)[between]
    resistivity = np.zeros(len(depth))
    resistivity[of_bulk] = 1.0 / conductivity[of_bulk]
    mean = 0.5 * (resistivity[:-1] + resistivity[1:])[between]
    return float(width.sum()), float((width * mean).sum())


def undepleted_layer_of_mesh(volumes, span, electrons, holes, net_doping, mu_n, mu_p):
    """The bulk of a device of two or three dimensions that is not depleted:
    its mean width [cm] and its resistance times its area [Ohm cm^2].

    `volumes` are the volumes of the nodes, the NodeVolume of DEVSIM: cm^2 in
    two dimensions, cm^3 in three. `span` is the extent of the mesh in the
    plane of the electrodes: its width [cm] in two dimensions, its area
    [cm^2] in three. The rest are as for `conductive`. Over the nodes of the
    undepleted bulk, as `_of_undepleted_bulk` judges them, the width is
    sum(V_i) / span and the resistance times the area sum(rho_i V_i) / span,
    rho_i the resistivity of the node [Ohm cm]. A fully depleted device has
    no such node: both values are 0.
    """
    if not span > 0:
        raise ValueError(f"the mesh spans {span} in the plane of the electrodes: its span is zero")
    of_bulk, conductivity = _of_undepleted_bulk(electrons, holes, net_doping, mu_n, mu_p)
    if not of_bulk.any():
        return 0.0, 0.0
    volumes = np.asarray(volumes, dtype=float)[of_bulk]
    resistivity = 1.0 / conductivity[of_bulk]
    return float(volumes.sum() / span), float((resistivity * volumes).sum() / span)
