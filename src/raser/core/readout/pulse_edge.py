"""Which way the pulse of each output goes, as the device and the chain make it."""

import numpy as np

from raser.core.field.device_circuit import planar_circuit

from .spice import solve


def collected_charge_sign(my_d, electrode):
    """Sign of the charge a read-out electrode of a device collects: -1 for
    electrons, which the electrode at the higher potential collects, +1 for
    holes.

    The bias of the device file is on its electrode "electrode" at "voltage";
    the other electrodes are on ground.
    """
    bias = my_d.device_dict["bias"]
    voltage = float(bias["voltage"])
    # the read-out electrode over the other one
    above = voltage if bias["electrode"] == electrode else -voltage
    if above == 0:
        raise ValueError(
            f"{electrode} of {my_d.det_name} and its other electrode are at one potential"
        )
    return -1 if above > 0 else 1


# a chain whose output moves less than this for 1 fC does not answer it [V]
NO_ANSWER_V = 1e-9


def chain_sign(chain):
    """+1 when the chain answers a positive charge on its input with a pulse
    whose largest swing from where its output rests is upwards, -1 when it
    is downwards: the chain inverts. Found by solving the chain on 1 pF for
    1 fC; a chain that does not answer is an error."""
    dt = 10e-12
    current = np.zeros((1, 2000))
    current[0, 5] = 1e-15 / dt
    voltage = solve(chain, ["probe"], dt, current, planar_circuit("probe", 1e-12))[0]
    # the first bin is before the charge: the output at rest
    swing = voltage - voltage[0]
    largest = swing[np.argmax(np.abs(swing))]
    if abs(largest) < NO_ANSWER_V:
        raise ValueError(
            f"The chain moves its output by {largest:.3g} V for 1 fC: it does "
            "not answer, so the way its pulses go is not known"
        )
    return 1 if largest > 0 else -1


def pulse_edges(my_d, chain, outputs):
    """For each output, in their order: "rising" when its pulse goes up,
    "falling" when it goes down, as the charge its electrode collects and
    the sign of the chain make it.

    A device that lists one read-out electrode for each output has them in
    the order of the outputs; one that repeats a single electrode, along a
    row or over the RC nodes of a resistive layer, reads that one everywhere.
    """
    contacts = [contact["name"] for contact in my_d.read_out_contact]
    if len(contacts) == 1:
        contacts = contacts * len(outputs)
    if len(contacts) != len(outputs):
        raise ValueError(
            f"{my_d.det_name} lists the read-out electrodes {contacts}, not one "
            f"for each of the outputs {list(outputs)}"
        )
    sign = chain_sign(chain)
    return [
        "rising" if collected_charge_sign(my_d, contact) * sign > 0 else "falling"
        for contact in contacts
    ]
