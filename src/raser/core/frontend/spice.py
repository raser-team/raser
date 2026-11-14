"""Solve the sensor, the amplifier stages and the load in one ngspice netlist."""

import subprocess
import tempfile
from pathlib import Path

import numpy as np


def write_netlist(stage_files, times, currents, sensor, load_ohm, raw):
    """Netlist of one transient run.

    The sensor, the amplifier stages and the load follow one another. Each
    stage is the subcircuit ``.subckt <stem of its file> in out``; stage_files
    lists them from the sensor to the load, and every electrode gets its own
    copy of each.
    Electrode k (from 1) has the nodes ``s<k>`` and ``r<k>``, the two ends of
    its induced current source, ``in<k>``, the input of its first stage, and
    ``out<k>``, the output of its last stage. Ground is node 0.

    times : bin centres of the induced currents [s], uniform.
    currents : induced currents [A], shape (electrodes, bins). A positive
        current flows from ``s<k>`` to ``r<k>`` through the source.
    sensor : SPICE lines of the sensor between the ``s<k>``, the ``r<k>``, the
        ``in<k>`` and ground.
    load_ohm : resistance from each ``out<k>`` to ground [Ohm].
    raw : file ngspice writes the ``v(out<k>)`` to.

    The run starts one bin before the first bin, with the circuit at rest and
    no current in that bin, and lasts to the end of the time axis, with the
    bin width as step.
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
    since_start = times - times[0] + 1.5 * step

    stage_files = [Path(stage_file).resolve() for stage_file in stage_files]
    lines = [" > ".join(["sensor", *(f.stem for f in stage_files), "load"])]
    lines.extend(f'.include "{stage_file}"' for stage_file in stage_files)
    outputs = []
    for k, current in enumerate(currents, start=1):
        # the bin added in front carries no current: ngspice takes the first
        # value of a source as a current that has been flowing forever
        points = f"{step / 2:.9g} 0 " + " ".join(
            f"{t:.9g} {i:.9g}" for t, i in zip(since_start, current)
        )
        lines.append(f"I{k} s{k} r{k} PWL({points})")
        # the output of a stage is the input of the next one
        nodes = [f"in{k}"]
        nodes.extend(f"in{k}_{j}" for j in range(2, len(stage_files) + 1))
        nodes.append(f"out{k}")
        for j, stage_file in enumerate(stage_files):
            lines.append(f"X{k}_{j + 1} {nodes[j]} {nodes[j + 1]} {stage_file.stem}")
        lines.append(f"Rload{k} out{k} 0 {load_ohm:.9g}")
        outputs.append(f"v(out{k})")
    lines.extend(sensor)
    lines.extend(
        [
            ".control",
            f"tran {step:.9g} {step * (times.size + 1):.9g}",
            f"wrdata {raw} {' '.join(outputs)}",
            ".endc",
            ".end",
        ]
    )
    return "\n".join(lines) + "\n"


def solve(stage_files, times, currents, sensor, load_ohm):
    """Output voltages [V] on the bins of the induced currents, shape
    (electrodes, bins). The arguments are those of write_netlist."""
    times = np.asarray(times, dtype=np.float64)
    with tempfile.TemporaryDirectory() as folder:
        raw = Path(folder) / "out.raw"
        netlist = Path(folder) / "run.cir"
        netlist.write_text(
            write_netlist(stage_files, times, currents, sensor, load_ohm, raw),
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
    since_start = times - times[0] + 1.5 * step
    return np.array(
        [
            np.interp(since_start, solved_times, data[:, column])
            for column in range(1, data.shape[1], 2)
        ]
    )
