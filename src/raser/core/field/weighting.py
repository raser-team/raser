"""The conductive part of a biased device in the solve of its weighting field."""

import pickle

import devsim
import numpy as np
from scipy.spatial import cKDTree

from .model_create import CreateEdgeModel
from .model_create import CreateEdgeModelDerivatives

# The permittivity of an edge between two conductive nodes, in units of the
# permittivity of the dielectric: what is left of the weighting potential
# inside a conductor is of the order of one over this.
CONDUCTOR_PERMITTIVITY = 1e10


def take_conductors_into_electrodes(device, region, conductive_file, cell_width=None):
    """Make the conductive nodes of `region` one potential with the electrode
    they touch, in a weighting field solve whose potential equation is set up.

    `conductive_file` is the Conductive_<bias>V.pkl of the solved field. Every
    node of the region must be among its points; the edges between two
    conductive nodes get CONDUCTOR_PERMITTIVITY times the permittivity, so a
    conductor that touches no electrode floats.

    Where the region is a row of cells and the field was solved on one of
    them, `cell_width` is the width of a cell in cm: the electric field
    repeats from cell to cell, and so does its conductive part.
    """
    with open(conductive_file, "rb") as stream:
        stored = pickle.load(stream)
    points = np.asarray(stored["points"], dtype=float).reshape(
        len(stored["points"]), -1
    )
    nodes = np.column_stack(
        [
            devsim.get_node_model_values(device=device, region=region, name=axis)
            for axis in "xyz"[: points.shape[1]]
        ]
    )
    if cell_width is not None:
        start = points[:, 1].min()
        nodes[:, 1] = start + (nodes[:, 1] - start) % cell_width
    distance, nearest = cKDTree(points).query(nodes)
    missing = distance > 1e-9 * np.ptp(points, axis=0).max()
    if missing.any():
        raise ValueError(
            f"{int(missing.sum())} of the {len(nodes)} nodes of {region} are not in {conductive_file}, "
            f"the first at {tuple(nodes[missing][0])} cm: the field was solved on another mesh"
        )
    devsim.node_solution(device=device, region=region, name="Conductive")
    devsim.set_node_values(
        device=device,
        region=region,
        name="Conductive",
        values=[float(value) for value in np.asarray(stored["values"], dtype=float)[nearest]],
    )
    devsim.edge_from_node_model(device=device, region=region, node_model="Conductive")
    flux = (
        f"Permittivity * (1 + {CONDUCTOR_PERMITTIVITY} * Conductive@n0 * Conductive@n1)"
        " * ElectricField"
    )
    for name in ("PotentialEdgeFlux", "contactcharge_edge"):
        CreateEdgeModel(device, region, name, flux)
        CreateEdgeModelDerivatives(device, region, name, flux, "Potential")
