"""A bias point that a field solve has saved, taken up again."""

from pathlib import Path

import devsim
import numpy as np

from .create_parameter import create_parameter
from .physics_drift_diffusion import GetContactBiasName
from .physics_irradiation import CARRIER_FLOOR
from .physics_irradiation import irradiation_defects
from .physics_irradiation import set_defect_parameters


def capacitance(my_d, folder, voltage, solver, irradiation_flux=None):
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
    for name in ("extended_solver", "extended_model", "extended_equation"):
        devsim.set_parameter(name=name, value=True)
    devsim.load_devices(file=str(saved))
    # The file keeps the mesh, the models and the solution, not the parameters.
    create_parameter(my_d, my_d.device, my_d.region)
    if devsim.get_material(device=my_d.device, region=my_d.region) == "Diamond":
        devsim.set_parameter(device=my_d.device, region=my_d.region, name="CarrierFloor", value=CARRIER_FLOOR)
    if "irradiation" in my_d.device_dict:
        irradiation = my_d.device_dict["irradiation"]
        if irradiation_flux is None:
            irradiation_flux = irradiation["irradiation_flux"]
        defects = irradiation_defects(my_d.device, my_d.region, irradiation["irradiation_model"])
        set_defect_parameters(my_d.device, my_d.region, defects, irradiation_flux)
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
