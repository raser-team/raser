"""The field of a device taken from a TCAD solution: a TDR file of Sentaurus,
solved at one bias, put into the field folder as a field solved at that bias.

The weighting field is not taken from TCAD. It is solved here on the mesh of
the file, as for a field solved by devsim: what conducts in the solution is
one potential with the electrode it touches, the rest is dielectric.
"""

import os
import pickle

import devsim
import h5py
import numpy as np

from .assets import field_pickle_path
from .conductive import conductive
from .create_mesh import mesh_axes
from .reading import Reading
from .save_milestone import save_milestone
from .save_milestone import save_record
from .save_milestone import save_solved
from .tdr_import import import_tdr
from .weighting import CONDUCTOR_PERMITTIVITY

MICROMETRE = 1e-4  # cm: a TDR file is in micrometres, a field folder in cm
# What the conductive part is judged from, as a TDR file names them.
CARRIERS = ("eDensity", "hDensity", "DopingConcentration", "eMobility", "hMobility")
METALS = ("Aluminum",)
PERMITTIVITY = {"Silicon": 11.9, "SiliconCarbide": 9.76, "Oxide": 3.9, "Nitride": 7.5}


def electrode_voltages(tdr):
    """The voltage on each electrode of the solution in `tdr`, in V, by the
    name the electrode has in the file."""
    with h5py.File(tdr, "r") as source:
        geometry = source["collection"]["geometry_0"]
        return {
            geometry[f"region_{int(dataset.attrs['region'])}"].attrs["name"].decode(): float(
                dataset["values"][0]
            )
            for dataset in geometry["state_0"].values()
            if dataset.attrs["name"].decode() == "ContactExternalVoltage"
        }


def bias_of(tdr, electrode, asked=None):
    """The bias the solution in `tdr` was solved at: the voltage the file
    holds for `electrode`, the electrode the device is biased on. `asked` is
    the bias of the command, if it gave one: it has to be that of the file,
    and is taken for a file that holds no electrode voltages."""
    voltages = electrode_voltages(tdr)
    if not voltages:
        if asked is None:
            raise ValueError(f"{tdr} holds no electrode voltages: give its bias with -bias")
        return float(asked)
    if electrode not in voltages:
        raise ValueError(
            f"{tdr} has no electrode {electrode}, the one the device is biased on; "
            f"its electrodes are {voltages}"
        )
    if asked is not None and float(asked) != voltages[electrode]:
        raise ValueError(
            f"{tdr} was solved with {voltages[electrode]} V on {electrode}, not at {asked} V"
        )
    return voltages[electrode]


def _nodes(device, region, dimension):
    """The nodes of a region, one row each, in the unit of the mesh."""
    return np.column_stack(
        [
            devsim.get_node_model_values(device=device, region=region, name=axis)
            for axis in "xyz"[:dimension]
        ]
    )


def conductive_nodes(device, region):
    """Which nodes of a region of a TCAD solution are conductive, 1.0 or 0.0
    each: a semiconductor by its carriers, its doping and the mobilities of
    the solution, a metal everywhere, another material nowhere."""
    material = devsim.get_material(device=device, region=region)
    stored = devsim.get_node_model_list(device=device, region=region)
    if material in METALS:
        return np.ones(len(devsim.get_node_model_values(device=device, region=region, name="x")))
    if "eDensity" not in stored and "hDensity" not in stored:
        return np.zeros(len(devsim.get_node_model_values(device=device, region=region, name="x")))
    missing = [name for name in CARRIERS if name not in stored]
    if missing:
        raise ValueError(
            f"the region {region} of the TCAD file holds no {', '.join(missing)}: "
            "its conductive part cannot be judged; plot eDensity, hDensity, Doping, "
            "eMobility and hMobility in the TCAD solve"
        )
    values = [
        np.array(devsim.get_node_model_values(device=device, region=region, name=name))
        for name in CARRIERS
    ]
    return conductive(*values).astype(float)


def set_up_weighting(device, dimension, is_conductive):
    """The equation of the weighting potential on every region of `device`,
    with `is_conductive` giving the conductive nodes of each region as 1.0 or
    0.0. Regions are joined across their interfaces. Every node at the place
    of an electrode node is held at the potential of that electrode, in
    whichever region it is: an electrode that lies on an interface holds both
    sides of it, where a contact equation of devsim holds only the side of
    its own region."""
    on_electrode = {}
    for contact in devsim.get_contact_list(device=device):
        (region,) = devsim.get_region_list(device=device, contact=contact)
        nodes = _nodes(device, region, dimension)
        for element in devsim.get_element_node_list(device=device, region=region, contact=contact):
            for node in element:
                on_electrode[tuple(nodes[node])] = contact
    held_by = {}
    for region in devsim.get_region_list(device=device):
        material = devsim.get_material(device=device, region=region)
        if material not in PERMITTIVITY and material not in METALS:
            raise ValueError(
                f"the region {region} of the TCAD file is of {material}, whose permittivity "
                f"is not known here (known: {sorted(PERMITTIVITY)})"
            )
        devsim.set_parameter(
            device=device, region=region, name="Permittivity", value=PERMITTIVITY.get(material, 1.0)
        )
        held_by[region] = [on_electrode.get(tuple(node)) for node in _nodes(device, region, dimension)]
        for name, values in (
            ("Conductive", [float(value) for value in is_conductive[region]]),
            ("Held", [float(contact is not None) for contact in held_by[region]]),
            ("HeldAt", [0.0] * len(held_by[region])),
            ("Potential", [0.0] * len(held_by[region])),
        ):
            devsim.node_solution(device=device, region=region, name=name)
            devsim.set_node_values(device=device, region=region, name=name, values=values)
        for name in ("Conductive", "Potential"):
            devsim.edge_from_node_model(device=device, region=region, node_model=name)
        stiffness = (
            f"Permittivity * (1 + {CONDUCTOR_PERMITTIVITY} * Conductive@n0 * Conductive@n1)"
            " * EdgeInverseLength"
        )
        for name, equation in (
            ("WeightingFlux", f"{stiffness} * (Potential@n0 - Potential@n1)"),
            ("WeightingFlux:Potential@n0", stiffness),
            ("WeightingFlux:Potential@n1", f"-{stiffness}"),
        ):
            devsim.edge_model(device=device, region=region, name=name, equation=equation)
        # A node on an electrode is held at its potential by a stiff spring.
        devsim.node_model(
            device=device, region=region, name="Hold", equation="1e20 * Held * (Potential - HeldAt)"
        )
        devsim.node_model(device=device, region=region, name="Hold:Potential", equation="1e20 * Held")
        devsim.equation(
            device=device,
            region=region,
            name="PotentialEquation",
            variable_name="Potential",
            edge_model="WeightingFlux",
            node_model="Hold",
            variable_update="default",
        )
    for interface in devsim.get_interface_list(device=device):
        for name, equation in (
            ("Continuous", "Potential@r0 - Potential@r1"),
            ("Continuous:Potential@r0", "1"),
            ("Continuous:Potential@r1", "-1"),
        ):
            devsim.interface_model(device=device, interface=interface, name=name, equation=equation)
        devsim.interface_equation(
            device=device,
            interface=interface,
            name="PotentialEquation",
            interface_model="Continuous",
            type="continuous",
        )
    return held_by


def solve_weighting(device, held_by, electrode):
    """The weighting potential of `electrode`, left in the node solution
    Potential of every region: 1 on that electrode, 0 on the others."""
    if electrode not in devsim.get_contact_list(device=device):
        raise ValueError(
            f"the TCAD file has no electrode {electrode} to read out; "
            f"its electrodes are {list(devsim.get_contact_list(device=device))}"
        )
    for region, contacts in held_by.items():
        devsim.set_node_values(
            device=device,
            region=region,
            name="HeldAt",
            values=[float(contact == electrode) for contact in contacts],
        )
    devsim.solve(type="dc", absolute_error=1e-6, relative_error=1e-6, maximum_iterations=20)


def _store(path, values, points, bias, dimension):
    with open(path, "wb") as file:
        pickle.dump(
            {
                "values": np.concatenate(values),
                "points": np.concatenate(points).tolist(),
                "metadata": {"voltage": bias, "dimension": dimension},
            },
            file,
        )


def import_field(tdr, my_d, folder, asked=None, flip=False):
    """Put the solution in `tdr` into `folder` as the field of `my_d` at the
    bias of the file, with its conductive part and the weighting potential of
    each read-out electrode, and list them in run.json as solved. Returns
    that bias."""
    my_d = Reading(my_d)
    bias = bias_of(tdr, my_d.device_dict["bias"]["electrode"], asked)
    dimension = my_d.dimension
    read_out = [electrode["name"] for electrode in my_d.device_dict["read_out_contact"]]
    try:
        device = import_tdr(tdr, os.path.join(folder, "converted.devsim"))
        save_milestone(device, bias, str(folder), dimension, None, False, is_tcad=True, is_flip=flip)
        regions = devsim.get_region_list(device=device)
        is_conductive = {region: conductive_nodes(device, region) for region in regions}
        points = [
            MICROMETRE * _nodes(device, region, dimension)[:, ::-1 if flip else 1]
            for region in regions
        ]
        _store(
            field_pickle_path(folder, "Conductive", bias),
            [is_conductive[region] for region in regions],
            points,
            bias,
            dimension,
        )
        held_by = set_up_weighting(device, dimension, is_conductive)
        for electrode in read_out:
            solve_weighting(device, held_by, electrode)
            os.makedirs(os.path.join(folder, "weightingfield", electrode), exist_ok=True)
            _store(
                field_pickle_path(os.path.join(folder, "weightingfield", electrode), "Potential", bias),
                [
                    np.array(devsim.get_node_model_values(device=device, region=region, name="Potential"))
                    for region in regions
                ],
                points,
                bias,
                dimension,
            )
    finally:
        devsim.reset_devsim()
    save_record(str(folder), axes=mesh_axes(my_d), read=my_d.read)
    save_solved(str(folder), "potential", bias)
    save_solved(str(folder), "weighting", bias)
    return bias
