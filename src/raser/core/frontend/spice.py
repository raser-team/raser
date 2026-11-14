"""Solve the sensor, the amplifier and its load in one ngspice netlist."""

import subprocess
import tempfile
from pathlib import Path

import numpy as np


def write_netlist(circuit_file, times, currents, sensor, load_ohm, raw):
    """Netlist of one transient run.

    The amplifier is the subcircuit ``.subckt <stem of circuit_file> in out``.
    Electrode k (from 1) has three nodes: ``s<k>``, where its induced current
    is injected, ``in<k>``, the input of its amplifier, and ``out<k>``, the
    output. Ground is node 0.

    times : bin centres of the induced currents [s], uniform.
    currents : induced currents [A], shape (electrodes, bins). A positive
        current flows from ``s<k>`` to ground.
    sensor : SPICE lines of the sensor between the ``s<k>``, the ``in<k>``
        and ground.
    load_ohm : resistance from each ``out<k>`` to ground [Ohm].
    raw : file ngspice writes the ``v(out<k>)`` to.

    The run starts at the left edge of the first bin and lasts the length of
    the time axis, with the bin width as step.
    """
    times = np.asarray(times, dtype=np.float64)
    currents = np.atleast_2d(np.asarray(currents, dtype=np.float64))
    if currents.shape[1] != times.size:
        raise ValueError(
            f"{currents.shape[1]} current samples for {times.size} time bins"
        )
    step = (times[-1] - times[0]) / (times.size - 1)
    if not np.allclose(np.diff(times), step, rtol=1e-6, atol=0.0):
        raise ValueError("The time axis of the induced currents must be uniform")
    since_start = times - times[0] + step / 2

    circuit_file = Path(circuit_file).resolve()
    lines = [f"{circuit_file.stem} with sensor and load", f'.include "{circuit_file}"']
    outputs = []
    for k, current in enumerate(currents, start=1):
        points = " ".join(f"{t:.9g} {i:.9g}" for t, i in zip(since_start, current))
        lines.append(f"I{k} s{k} 0 PWL({points})")
        lines.append(f"Xafe{k} in{k} out{k} {circuit_file.stem}")
        lines.append(f"Rload{k} out{k} 0 {load_ohm:.9g}")
        outputs.append(f"v(out{k})")
    lines.extend(sensor)
    lines.extend(
        [
            ".control",
            f"tran {step:.9g} {step * times.size:.9g}",
            f"wrdata {raw} {' '.join(outputs)}",
            ".endc",
            ".end",
        ]
    )
    return "\n".join(lines) + "\n"


def solve(circuit_file, times, currents, sensor, load_ohm):
    """Output voltages [V] on the bins of the induced currents, shape
    (electrodes, bins). The arguments are those of write_netlist."""
    times = np.asarray(times, dtype=np.float64)
    with tempfile.TemporaryDirectory() as folder:
        raw = Path(folder) / "out.raw"
        netlist = Path(folder) / "run.cir"
        netlist.write_text(
            write_netlist(circuit_file, times, currents, sensor, load_ohm, raw),
            encoding="utf-8",
        )
        subprocess.run(
            ["ngspice", "-b", str(netlist)],
            check=True,
            capture_output=True,
            text=True,
        )
        data = np.loadtxt(raw, dtype=np.float64, ndmin=2)
    # wrdata writes a time column before each vector
    solved_times = data[:, 0]
    step = (times[-1] - times[0]) / (times.size - 1)
    since_start = times - times[0] + step / 2
    return np.array(
        [
            np.interp(since_start, solved_times, data[:, column])
            for column in range(1, data.shape[1], 2)
        ]
    )
