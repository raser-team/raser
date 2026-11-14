"""Solve the sensor, the amplifier stages and the load in one ngspice netlist."""

import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class SensorCircuit:
    """The sensor as it stands in the netlist: once, for all electrodes.

    lines : SPICE lines of its elements. Ground is node 0.
    sources : for each electrode the two nodes (from, to) of its induced
        current source.
    outputs : for each electrode the node its first amplifier stage reads.

    The node names ``in<k>_<j>`` and ``out<k>`` belong to the stages.
    """

    lines: tuple[str, ...]
    sources: tuple[tuple[str, str], ...]
    outputs: tuple[str, ...]


def write_netlist(stage_files, times, currents, sensor, load_file, raw):
    """Netlist of one transient run.

    The sensor, the amplifier stages and the load follow one another. Each
    stage is the subcircuit ``.subckt <stem of its file> in out``; stage_files
    lists them from the sensor to the load. The load is the subcircuit
    ``.subckt <stem of load_file> in``. Every electrode gets its own copy of
    each stage and of the load.
    The first stage of electrode k (from 1) reads the output node the sensor
    gives for it; ``out<k>`` is the output of its last stage and the input of
    its load. Ground is node 0.

    times : bin centres of the induced currents [s], uniform.
    currents : induced currents [A], shape (electrodes, bins). A positive
        current flows through the source from the first to the second node
        the sensor gives for the electrode.
    sensor : SensorCircuit with as many electrodes as there are currents.
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
    if not len(sensor.sources) == len(sensor.outputs) == len(currents):
        raise ValueError(
            f"{len(currents)} currents for a sensor with {len(sensor.sources)} "
            f"current sources and {len(sensor.outputs)} outputs"
        )

    stage_files = [Path(stage_file).resolve() for stage_file in stage_files]
    load_file = Path(load_file).resolve()
    chain = [*stage_files, load_file]
    lines = [" > ".join(["sensor", *(f.stem for f in chain)])]
    lines.extend(f'.include "{file}"' for file in chain)
    outputs = []
    for k, current in enumerate(currents, start=1):
        # the bin added in front carries no current: ngspice takes the first
        # value of a source as a current that has been flowing forever
        points = f"{step / 2:.9g} 0 " + " ".join(
            f"{t:.9g} {i:.9g}" for t, i in zip(since_start, current)
        )
        source_from, source_to = sensor.sources[k - 1]
        lines.append(f"I{k} {source_from} {source_to} PWL({points})")
        # the output of a stage is the input of the next one
        nodes = [sensor.outputs[k - 1]]
        nodes.extend(f"in{k}_{j}" for j in range(2, len(stage_files) + 1))
        nodes.append(f"out{k}")
        for j, stage_file in enumerate(stage_files):
            lines.append(f"X{k}_{j + 1} {nodes[j]} {nodes[j + 1]} {stage_file.stem}")
        lines.append(f"Xload{k} out{k} {load_file.stem}")
        outputs.append(f"v(out{k})")
    lines.extend(sensor.lines)
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


def solve(stage_files, times, currents, sensor, load_file):
    """Output voltages [V] on the bins of the induced currents, shape
    (electrodes, bins). The arguments are those of write_netlist."""
    times = np.asarray(times, dtype=np.float64)
    with tempfile.TemporaryDirectory() as folder:
        raw = Path(folder) / "out.raw"
        netlist = Path(folder) / "run.cir"
        netlist.write_text(
            write_netlist(stage_files, times, currents, sensor, load_file, raw),
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
