"""A bias point that a field solve has saved, taken up again."""

import json
from pathlib import Path

import devsim
import numpy as np

from .physics_drift_diffusion import GetContactBiasName


def _plain(names, value_of):
    """The parameters among `names` whose value json can hold as it is."""
    kept = {}
    for name in names:
        value = value_of(name)
        if isinstance(value, (bool, int, float, str)):
            kept[name] = value
    return kept


def parameters_file(saved):
    """<V>V.parameters.json beside the saved <V>V.devsim."""
    saved = Path(saved)
    return saved.with_name(saved.name[: -len(".devsim")] + ".parameters.json")


def save_point(device, saved):
    """Write the state of `device` into `saved`, a <V>V.devsim file, and every
    parameter devsim holds into <V>V.parameters.json beside it: the file of
    devsim keeps the mesh, the models and the solution, not the parameters."""
    devsim.write_devices(file=str(saved), type="devsim")
    parameters = {
        "global": _plain(devsim.get_parameter_list(), lambda name: devsim.get_parameter(name=name)),
        "device": _plain(
            devsim.get_parameter_list(device=device),
            lambda name: devsim.get_parameter(device=device, name=name),
        ),
        "regions": {
            region: _plain(
                devsim.get_parameter_list(device=device, region=region),
                lambda name, region=region: devsim.get_parameter(device=device, region=region, name=name),
            )
            for region in devsim.get_region_list(device=device)
        },
    }
    with open(parameters_file(saved), "w") as stream:
        json.dump(parameters, stream, indent=1)


def load_point(device, saved):
    """Read the state `save_point` wrote back into devsim: the global
    parameters, the device, then its parameters and those of its regions."""
    saved = Path(saved)
    if not parameters_file(saved).exists():
        raise FileNotFoundError(
            f"{saved} has no {parameters_file(saved).name} beside it: the point was "
            "saved without its parameters and has to be solved again"
        )
    with open(parameters_file(saved)) as stream:
        parameters = json.load(stream)
    for name, value in parameters["global"].items():
        devsim.set_parameter(name=name, value=value)
    devsim.load_devices(file=str(saved))
    for name, value in parameters["device"].items():
        devsim.set_parameter(device=device, name=name, value=value)
    for region, of_region in parameters["regions"].items():
        for name, value in of_region.items():
            devsim.set_parameter(device=device, region=region, name=name, value=value)


def capacitance(my_d, folder, voltage, solver):
    """The specific capacitance at one saved bias in V, as the mesh gives it:
    pF/cm^2 of a one-dimensional mesh, pF/cm of a two-dimensional one, pF of
    a three-dimensional one. The saved state is read back, settled at its
    bias, and given one small-signal solve."""
    saved = Path(folder) / f"{float(voltage)}V.devsim"
    if not saved.exists():
        have = sorted(point.name for point in Path(folder).glob("*V.devsim"))
        raise FileNotFoundError(f"no field saved at {voltage} V in {folder}: {have}")
    bias = my_d.device_dict["bias"]["electrode"]
    frequency = float(my_d.device_dict.get("frequency", solver["ac"]["frequency"]))
    step = solver["voltage_step"]
    # The saved contact equations name the circuit node, so the source comes first.
    devsim.circuit_element(
        name="V1",
        n1=GetContactBiasName(bias),
        n2=0,
        value=0.0,
        acreal=float(solver["ac"]["real"]),
        acimag=float(solver["ac"]["imaginary"]),
    )
    load_point(my_d.device, saved)
    for contact in devsim.get_contact_list(device=my_d.device):
        devsim.set_parameter(
            device=my_d.device,
            name=GetContactBiasName(contact),
            value=float(voltage) if contact == bias else 0.0,
        )
    devsim.solve(
        type="dc",
        absolute_error=float(step["absolute_error"]),
        relative_error=float(step["relative_error"]),
        maximum_iterations=int(step["maximum_iterations"]),
    )
    devsim.circuit_alter(name="V1", value=float(voltage))
    devsim.solve(type="ac", frequency=frequency)
    current = devsim.get_circuit_node_value(node="V1.I", solution="ssac_imag")
    return 1e12 * current / (-2 * np.pi * frequency), frequency
