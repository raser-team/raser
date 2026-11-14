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
