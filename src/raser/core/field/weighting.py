"""The conductive part of a biased device in the solve of its weighting field."""

import pickle

import devsim
import numpy as np

from .model_create import CreateEdgeModel
from .model_create import CreateEdgeModelDerivatives

# The permittivity of an edge between two conductive nodes, in units of the
# permittivity of the dielectric: what is left of the weighting potential
# inside a conductor is of the order of one over this.
CONDUCTOR_PERMITTIVITY = 1e10


def take_conductors_into_electrodes(device, region, conductive_file):
    """Make the conductive nodes of `region` one potential with the electrode
    they touch, in a weighting field solve whose potential equation is set up.

    `conductive_file` is the Conductive_<bias>V.pkl of the solved field. Every
    node of the region must be among its points; the edges between two
    conductive nodes get CONDUCTOR_PERMITTIVITY times the permittivity, so a
    conductor that touches no electrode floats.
    """
    with open(conductive_file, "rb") as stream:
        stored = pickle.load(stream)
    points = np.asarray(stored["points"], dtype=float).reshape(
        len(stored["points"]), -1
    )
    saved = {
        tuple(point): value for point, value in zip(points.tolist(), stored["values"])
    }
    nodes = np.column_stack(
        [
            devsim.get_node_model_values(device=device, region=region, name=axis)
            for axis in "xyz"[: points.shape[1]]
        ]
    )
    missing = [node for node in map(tuple, nodes.tolist()) if node not in saved]
    if missing:
        raise ValueError(
            f"{len(missing)} of the {len(nodes)} nodes of {region} are not in {conductive_file}, "
            f"the first at {missing[0]} cm: the field was solved on another mesh"
        )
    devsim.node_solution(device=device, region=region, name="Conductive")
    devsim.set_node_values(
        device=device,
        region=region,
        name="Conductive",
        values=[float(saved[node]) for node in map(tuple, nodes.tolist())],
    )
    devsim.edge_from_node_model(device=device, region=region, node_model="Conductive")
    flux = (
        f"Permittivity * (1 + {CONDUCTOR_PERMITTIVITY} * Conductive@n0 * Conductive@n1)"
        " * ElectricField"
    )
    for name in ("PotentialEdgeFlux", "contactcharge_edge"):
        CreateEdgeModel(device, region, name, flux)
        CreateEdgeModelDerivatives(device, region, name, flux, "Potential")
