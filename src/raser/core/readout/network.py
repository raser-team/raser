"""Response of the network of a resistive layer to an impulse on a point of
the device, and admittance between its read-outs."""

import subprocess
import tempfile
from pathlib import Path

import numpy as np

from raser.core.field.resistive_layer import shares

from .spice import _ngspice, solve


def impulse_response(
    my_d, circuit, chain, points_um, dt=10e-12, bins=2000, charge=1e-15
):
    """Output voltages [V] of the read-outs of a device with a resistive
    layer for a charge injected at each of several points, shape
    (points, outputs, bins), the outputs in the order of circuit.outputs.

    my_d : the Detector, whose electrodes are the RC nodes of the layer.
    circuit : DeviceCircuit of the device, its sources those of the RC nodes.
    chain : the amplifier chain, as named_chain gives it.
    points_um : the points, each as shares takes it.
    dt : width of a time bin [s].
    bins : number of time bins.
    charge : the charge [C], injected as a rectangular current pulse in the
        first bin, shared among the RC nodes as shares gives it.
    """
    rc_nodes = list(circuit.sources)
    count = int(my_d.x_ele_num) * int(my_d.y_ele_num)
    if len(rc_nodes) != count:
        raise ValueError(
            f"The circuit has the currents of {len(rc_nodes)} RC nodes, and "
            f"{my_d.det_name} has {count}"
        )
    voltages = []
    for point_um in points_um:
        currents = np.zeros((count, bins))
        for number, part in shares(my_d, point_um).items():
            currents[number, 0] = part * charge / dt
        voltages.append(solve(chain, rc_nodes, dt, currents, circuit))
    return np.array(voltages)


def _port_netlist(circuit, driven, frequencies_hz, raws):
    """Netlist of the AC analysis of the circuit with 1 V on the read-out
    driven and the other read-outs on AC ground, the induced current sources
    open. raws are the files ngspice writes the currents of the voltage
    sources to, one per frequency, as frequency, real and imaginary part of
    each, in the order of circuit.outputs."""
    lines = ["device > ports", *circuit.lines]
    vectors = []
    for k, node in enumerate(circuit.outputs.values()):
        lines.append(f"Vport{k} {node} 0 dc 0 ac {1 if k == driven else 0}")
        vectors.append(f"i(Vport{k})")
    lines.append(".control")
    for frequency, raw in zip(frequencies_hz, raws):
        lines.append(f"ac lin 1 {frequency:.17g} {frequency:.17g}")
        lines.append(f"wrdata {raw} {' '.join(vectors)}")
    lines.extend([".endc", ".end"])
    return "\n".join(lines) + "\n"


def admittance(circuit, frequencies_hz):
    """Admittance [S] between the read-outs of the circuit of a device, as
    ngspice's AC small-signal analysis gives it, shape (frequencies, outputs,
    outputs), complex, the outputs in the order of circuit.outputs. Y[f, i, j]
    is the current [A] that flows from outside into the i-th read-out when 1 V
    of AC is put on the j-th, the other read-outs on AC ground and the induced
    current sources open.

    circuit : DeviceCircuit.
    frequencies_hz : increasing positive frequencies [Hz].
    """
    frequencies = np.asarray(frequencies_hz, dtype=np.float64)
    if frequencies.ndim != 1 or frequencies.size == 0:
        raise ValueError("The admittance needs a non-empty list of frequencies")
    if np.any(frequencies <= 0):
        raise ValueError("The frequencies of the admittance must be positive")
    if np.any(np.diff(frequencies) <= 0):
        raise ValueError("The frequencies of the admittance must increase")
    count = len(circuit.outputs)
    result = np.empty((frequencies.size, count, count), dtype=np.complex128)
    with tempfile.TemporaryDirectory() as folder:
        for driven in range(count):
            raws = [
                Path(folder) / f"ac{driven}_{n}.raw" for n in range(frequencies.size)
            ]
            netlist = Path(folder) / f"ac{driven}.cir"
            netlist.write_text(
                _port_netlist(circuit, driven, frequencies, raws), encoding="utf-8"
            )
            subprocess.run(
                [_ngspice(), "-b", str(netlist)],
                check=True,
                capture_output=True,
                text=True,
            )
            for n, raw in enumerate(raws):
                # wrdata writes the frequency, the real and the imaginary part
                # of each vector
                data = np.loadtxt(raw, dtype=np.float64, ndmin=2)[0]
                currents = data[1::3] + 1j * data[2::3]
                # the current of a voltage source flows through it from the
                # positive node; what flows into the device is the opposite
                result[n, :, driven] = -currents
    return result
