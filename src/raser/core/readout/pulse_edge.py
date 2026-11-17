"""Which way the pulse of each output goes, as the device and the chain make it."""

import numpy as np

from raser.core.field.device_circuit import planar_circuit

from .spice import solve


def collected_charge_sign(my_d):
    """Sign of the charge the read-out electrodes of a device collect: -1
    for electrons, which the electrode at the higher potential collects, +1
    for holes.

    The bias of the device file is on its electrode "electrode" at "voltage";
    the other electrodes are on ground.
    """
    bias = my_d.device_dict["bias"]
    voltage = float(bias["voltage"])
    read_out = {contact["name"] for contact in my_d.read_out_contact}
    # the read-out electrodes over the other one
    above = voltage if bias["electrode"] in read_out else -voltage
    if above == 0:
        raise ValueError(
            f"{my_d.det_name} has its read-out and its other electrode at one potential"
        )
    return -1 if above > 0 else 1


def chain_sign(chain):
    """+1 when the chain answers a positive charge on its input with a pulse
    whose largest swing is positive, -1 when that swing is negative: the
    chain inverts. Found by solving the chain on 1 pF for 1 fC."""
    dt = 10e-12
    current = np.zeros((1, 2000))
    current[0, 5] = 1e-15 / dt
    voltage = solve(chain, ["probe"], dt, current, planar_circuit("probe", 1e-12))[0]
    return 1 if voltage[np.argmax(np.abs(voltage))] > 0 else -1


def pulse_edges(my_d, chain, outputs):
    """For each output, in their order: "rising" when its pulse goes up,
    "falling" when it goes down, as the charge the device collects and the
    sign of the chain make it."""
    up = collected_charge_sign(my_d) * chain_sign(chain) > 0
    return ["rising" if up else "falling"] * len(outputs)
