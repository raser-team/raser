"""The conductive part of a biased device in the solve of its weighting field."""

import pickle

import devsim
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree

from .model_create import CreateEdgeModel
from .model_create import CreateEdgeModelDerivatives

# The permittivity of an edge between two conductive nodes, in units of the
# permittivity of the dielectric: what is left of the weighting potential
# inside a conductor is of the order of one over this.
CONDUCTOR_PERMITTIVITY = 1e10


def joined_electrodes(conductive, edges, contact_nodes):
    """The conductive pieces that touch two or more electrodes.

    `conductive` is a bool array, one entry per node; `edges` is an (m, 2)
    integer array of the node indices at the two ends of each mesh edge;
    `contact_nodes` maps an electrode name to the indices of the nodes it
    touches. Only an edge with a conductive node at both ends carries a
    conductive piece from one node to the next. A piece that touches one
    electrode at several nodes is still one electrode.

    Returns a list of (names, nodes): the sorted names of the electrodes the
    piece touches and the indices of all its nodes.
    """
    conductive = np.asarray(conductive, dtype=bool)
    edges = np.asarray(edges, dtype=int).reshape(-1, 2)
    count = len(conductive)
    inside = conductive[edges[:, 0]] & conductive[edges[:, 1]]
    edges = edges[inside]
    graph = coo_matrix(
        (np.ones(len(edges)), (edges[:, 0], edges[:, 1])), shape=(count, count)
    )
    _, label = connected_components(graph, directed=False)
    touched = {}
    for name, indices in contact_nodes.items():
        for index in indices:
            if conductive[index]:
                touched.setdefault(int(label[index]), set()).add(name)
    joined = []
    for piece in sorted(touched):
        names = tuple(sorted(touched[piece]))
        if len(names) >= 2:
            nodes = np.flatnonzero(conductive & (label == piece))
            joined.append((names, nodes))
    return joined


def take_conductors_into_electrodes(device, region, conductive_file, *, bias, cell_width=None):
    """Make the conductive nodes of `region` one potential with the electrode
    they touch, in a weighting field solve whose potential equation is set up.

    `conductive_file` is the Conductive_<bias>V.pkl of the solved field. Every
    node of the region must be among its points; the edges between two
    conductive nodes get CONDUCTOR_PERMITTIVITY times the permittivity, so a
    conductor that touches no electrode floats. A conductive piece that
    touches two electrodes is an error. `bias` (V) only names the solve in
    that error.

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
    devsim.edge_from_node_model(device=device, region=region, node_model="node_index")
    edges = np.column_stack(
        [
            np.asarray(
                devsim.get_edge_model_values(
                    device=device, region=region, name=f"node_index@n{end}"
                )
            ).astype(int)
            for end in (0, 1)
        ]
    )
    contact_nodes = {}
    for name in devsim.get_contact_list(device=device):
        elements = devsim.get_element_node_list(device=device, region=region, contact=name)
        indices = {int(index) for element in elements for index in element}
        if indices:
            contact_nodes[name] = indices
    conductive = np.asarray(
        devsim.get_node_model_values(device=device, region=region, name="Conductive")
    ) > 0.5
    joined = joined_electrodes(conductive, edges, contact_nodes)
    if joined:
        names, piece = joined[0]
        coordinates = np.column_stack(
            [
                devsim.get_node_model_values(device=device, region=region, name=axis)
                for axis in "xyz"[: points.shape[1]]
            ]
        )[piece]
        lo = tuple(float(f"{value:.4g}") for value in coordinates.min(axis=0))
        hi = tuple(float(f"{value:.4g}") for value in coordinates.max(axis=0))
        joined_names = " and ".join(names) if len(names) == 2 else ", ".join(names)
        raise ValueError(
            f"at {bias} V a conductive piece of {region} joins the electrodes {joined_names}: "
            f"{len(piece)} nodes, from {lo} to {hi} cm; "
            "it makes them one conductor and their capacitance about CONDUCTOR_PERMITTIVITY times too large. "
            "See the criterion of the conductive part in core/field"
        )
    devsim.edge_from_node_model(device=device, region=region, node_model="Conductive")
    flux = (
        f"Permittivity * (1 + {CONDUCTOR_PERMITTIVITY} * Conductive@n0 * Conductive@n1)"
        " * ElectricField"
    )
    for name in ("PotentialEdgeFlux", "contactcharge_edge"):
        CreateEdgeModel(device, region, name, flux)
        CreateEdgeModelDerivatives(device, region, name, flux, "Potential")
