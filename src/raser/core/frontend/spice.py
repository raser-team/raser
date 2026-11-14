"""Solve the sensor, the amplifier stages and the load in one ngspice netlist."""

import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .circuit import subcircuit


@dataclass(frozen=True)
class SensorCircuit:
    """The sensor as it stands in the netlist: once, for all electrodes.

    lines : SPICE lines of its elements. Ground is node 0.
    sources : for each electrode, by its name, the two nodes (from, to) of
        its induced current source.
    outputs : for each electrode, by its name, the node its first amplifier
        stage reads.

    The node names ``in<k>_<j>`` and ``out<k>`` belong to the stages.
    """

    lines: tuple[str, ...]
    sources: dict[str, tuple[str, str]]
    outputs: dict[str, str]


def _bin_centres(dt, bins):
    """Centres of the bins [s], counted from the start of the run, which is
    one bin before the first bin."""
    return (np.arange(bins) + 1.5) * dt


def _current_sources(electrodes, dt, currents, sensor):
    """Lines of the induced current sources.

    The run they are written for starts one bin before the first bin, with
    the circuit at rest and no current in that bin.
    """
    if not dt > 0:
        raise ValueError(f"The bin width must be positive, not {dt} s")
    since_start = _bin_centres(dt, currents.shape[1])
    if len(electrodes) != len(currents):
        raise ValueError(f"{len(currents)} currents for {len(electrodes)} electrodes")
    if not sorted(electrodes) == sorted(sensor.sources) == sorted(sensor.outputs):
        raise ValueError(
            f"The currents are of the electrodes {list(electrodes)}; the sensor "
            f"has current sources for {list(sensor.sources)} and outputs for "
            f"{list(sensor.outputs)}"
        )
    lines = []
    for k, (electrode, current) in enumerate(zip(electrodes, currents), start=1):
        # the bin added in front carries no current: ngspice takes the first
        # value of a source as a current that has been flowing forever
        points = f"{dt / 2:.9g} 0 " + " ".join(
            f"{t:.9g} {i:.9g}" for t, i in zip(since_start, current)
        )
        source_from, source_to = sensor.sources[electrode]
        lines.append(f"I{k} {source_from} {source_to} PWL({points})")
    return lines


def _transient(dt, bins, raw, vectors):
    """Control lines of the run: one bin more than the currents have."""
    return [
        ".control",
        f"tran {dt:.9g} {dt * (bins + 1):.9g}",
        f"wrdata {raw} {' '.join(vectors)}",
        ".endc",
        ".end",
    ]


def _run(netlist_text, raw, dt, bins):
    """Run ngspice on the netlist and return the vectors it wrote to raw on
    the bins of the induced currents, shape (vectors, bins)."""
    netlist = Path(raw).with_name("run.cir")
    netlist.write_text(netlist_text, encoding="utf-8")
    subprocess.run(
        ["ngspice", "-b", str(netlist)],
        check=True,
        capture_output=True,
        text=True,
    )
    data = np.loadtxt(raw, dtype=np.float64, ndmin=2)
    # wrdata writes a time column before each vector
    solved_times = data[:, 0]
    since_start = _bin_centres(dt, bins)
    return np.array(
        [
            np.interp(since_start, solved_times, data[:, column])
            for column in range(1, data.shape[1], 2)
        ]
    )


def write_netlist(chain, electrodes, dt, currents, sensor, raw):
    """Netlist of one transient run.

    The sensor, the amplifier stages and the load follow one another.
    chain["stages"] holds the stages under their names, from the sensor to the
    load, and chain["load"] the load, each as circuit.subcircuit describes
    them: a stage with the ports "in" and "out", the load with the port "in".
    Every electrode gets its own copy of each stage and of the load.
    The models a stage or the load brings stand once in the netlist.
    The first stage of the k-th electrode (from 1) reads the output node the
    sensor gives for it; ``out<k>`` is the output of its last stage and the
    input of its load. Ground is node 0.

    electrodes : names of the electrodes, in the order of the rows of
        currents. They have to be the electrodes of the sensor.
    dt : width of a time bin of the induced currents [s].
    currents : induced currents [A], shape (electrodes, bins), each value the
        mean current in its bin. A positive current flows through the source
        from the first to the second node the sensor gives for the electrode.
    sensor : SensorCircuit.
    raw : file ngspice writes the ``v(out<k>)`` to.

    The run starts one bin before the first bin, with the circuit at rest and
    no current in that bin, and lasts to the end of the last bin, with the
    bin width as step.
    """
    currents = np.atleast_2d(np.asarray(currents, dtype=np.float64))
    sources = _current_sources(electrodes, dt, currents, sensor)

    stages = chain["stages"]
    if "load" in stages:
        raise ValueError('A stage cannot be named "load"')
    lines = [" > ".join(["sensor", *stages, "load"])]
    models: list[list[str]] = []
    for part in (*stages.values(), chain["load"]):
        if "models" in part and part["models"] not in models:
            models.append(part["models"])
    for block in models:
        lines.extend(block)
    lines.extend(subcircuit(name, stage).rstrip() for name, stage in stages.items())
    lines.append(subcircuit("load", chain["load"]).rstrip())
    lines.extend(sources)
    outputs = []
    for k, electrode in enumerate(electrodes, start=1):
        # the output of a stage is the input of the next one
        nodes = [sensor.outputs[electrode]]
        nodes.extend(f"in{k}_{j}" for j in range(2, len(stages) + 1))
        nodes.append(f"out{k}")
        for j, name in enumerate(stages):
            lines.append(f"X{k}_{j + 1} {nodes[j]} {nodes[j + 1]} {name}")
        lines.append(f"Xload{k} out{k} load")
        outputs.append(f"v(out{k})")
    lines.extend(sensor.lines)
    lines.extend(_transient(dt, currents.shape[1], raw, outputs))
    return "\n".join(lines) + "\n"


def solve(chain, electrodes, dt, currents, sensor):
    """Output voltages [V] on the bins of the induced currents, shape
    (electrodes, bins), in the order of electrodes. The arguments are those of
    write_netlist."""
    currents = np.atleast_2d(np.asarray(currents, dtype=np.float64))
    with tempfile.TemporaryDirectory() as folder:
        raw = Path(folder) / "out.raw"
        netlist = write_netlist(chain, electrodes, dt, currents, sensor, raw)
        return _run(netlist, raw, dt, currents.shape[1])


def write_short_circuit_netlist(electrodes, dt, currents, sensor, raw):
    """Netlist of one transient run of the sensor alone, with each of its
    outputs shorted to ground. electrodes, dt, currents and sensor are those of
    write_netlist; raw is the file ngspice writes the currents in the shorts
    to."""
    currents = np.atleast_2d(np.asarray(currents, dtype=np.float64))
    sources = _current_sources(electrodes, dt, currents, sensor)
    lines = ["sensor > short", *sources]
    shorts = []
    for k, electrode in enumerate(electrodes, start=1):
        lines.append(f"Vshort{k} {sensor.outputs[electrode]} 0 0")
        shorts.append(f"i(Vshort{k})")
    lines.extend(sensor.lines)
    lines.extend(_transient(dt, currents.shape[1], raw, shorts))
    return "\n".join(lines) + "\n"


def short_circuit_currents(electrodes, dt, currents, sensor):
    """Currents [A] the sensor drives into a short at each of its outputs, on
    the bins of the induced currents, shape (electrodes, bins), in the order
    of electrodes. A positive current flows from the output node into the
    short."""
    currents = np.atleast_2d(np.asarray(currents, dtype=np.float64))
    with tempfile.TemporaryDirectory() as folder:
        raw = Path(folder) / "out.raw"
        netlist = write_short_circuit_netlist(electrodes, dt, currents, sensor, raw)
        return _run(netlist, raw, dt, currents.shape[1])
