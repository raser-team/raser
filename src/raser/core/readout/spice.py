"""Solve the device, the amplifier stages and the load in one ngspice netlist."""

import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np

from raser.supports.dependency import MissingDependency

from .circuit import subcircuit


def _bin_centres(dt, bins):
    """Centres of the bins [s], counted from the start of the run, which is
    one bin before the first bin."""
    return (np.arange(bins) + 1.5) * dt


def _current_sources(electrodes, dt, currents, circuit):
    """Lines of the induced current sources.

    The run they are written for starts one bin before the first bin, with
    the circuit at rest and no current in that bin.
    """
    if not dt > 0:
        raise ValueError(f"The bin width must be positive, not {dt} s")
    since_start = _bin_centres(dt, currents.shape[1])
    if len(electrodes) != len(currents):
        raise ValueError(f"{len(currents)} currents for {len(electrodes)} electrodes")
    if sorted(electrodes) != sorted(circuit.sources):
        raise ValueError(
            f"The currents are of the electrodes {list(electrodes)}; the device "
            f"has current sources for {list(circuit.sources)}"
        )
    lines = []
    for k, (electrode, current) in enumerate(zip(electrodes, currents), start=1):
        # the bin added in front carries no current: ngspice takes the first
        # value of a source as a current that has been flowing forever
        points = f"{dt / 2:.9g} 0 " + " ".join(
            f"{t:.9g} {i:.9g}" for t, i in zip(since_start, current)
        )
        source_from, source_to = circuit.sources[electrode]
        lines.append(f"I{k} {source_from} {source_to} PWL({points})")
    return lines


def _transient(dt, bins, raw, vectors):
    """Control lines of the run: one bin more than the currents have. Only
    the vectors written are kept: ngspice keeps every node of every step
    otherwise, which a row of some hundred strips does not fit in.

    The integration is Gear's: with the trapezoidal default, ngspice 41
    does not return when the depletion capacitances meet at a shared node
    that goes to ground through a resistor, its step collapsing."""
    return [
        ".options method=gear",
        f".save {' '.join(vectors)}",
        ".control",
        f"tran {dt:.9g} {dt * (bins + 1):.9g}",
        f"wrdata {raw} {' '.join(vectors)}",
        ".endc",
        ".end",
    ]


def _ngspice():
    """The ngspice program, or what is missing and how to get it."""
    program = shutil.which("ngspice")
    if program is None:
        raise MissingDependency(
            "ngspice is not installed",
            "Install it with conda install -c conda-forge ngspice on x86 Linux, "
            "or with env/install-ngspice.sh on macOS arm64 and Linux aarch64",
        )
    return program


def _run(netlist_text, raw, dt, bins):
    """Run ngspice on the netlist and return the vectors it wrote to raw on
    the bins of the induced currents, shape (vectors, bins)."""
    netlist = Path(raw).with_name("run.cir")
    netlist.write_text(netlist_text, encoding="utf-8")
    subprocess.run(
        [_ngspice(), "-b", str(netlist)],
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


def _chain(chain, circuit):
    """Lines of the stages and the load behind each output of the device, with
    the device itself, and the node of the load of each output, in the order
    of circuit.outputs."""
    stages = chain["stages"]
    if "load" in stages:
        raise ValueError('A stage cannot be named "load"')
    lines = [" > ".join(["device", *stages, "load"])]
    models: list[list[str]] = []
    for part in (*stages.values(), chain["load"]):
        if "models" in part and part["models"] not in models:
            models.append(part["models"])
    for block in models:
        lines.extend(block)
    lines.extend(subcircuit(name, stage).rstrip() for name, stage in stages.items())
    lines.append(subcircuit("load", chain["load"]).rstrip())
    outputs = []
    for k, output in enumerate(circuit.outputs.values(), start=1):
        # the output of a stage is the input of the next one; without a
        # stage the load is on the device itself
        nodes = [output]
        if stages:
            nodes.extend(f"in{k}_{j}" for j in range(2, len(stages) + 1))
            nodes.append(f"out{k}")
        for j, name in enumerate(stages):
            lines.append(f"X{k}_{j + 1} {nodes[j]} {nodes[j + 1]} {name}")
        lines.append(f"Xload{k} {nodes[-1]} load")
        outputs.append(nodes[-1])
    lines.extend(circuit.lines)
    return lines, outputs


def write_netlist(chain, electrodes, dt, currents, circuit, raw):
    """Netlist of one transient run.

    The device, the amplifier stages and the load follow one another.
    chain["stages"] holds the stages under their names, from the device to the
    load, and chain["load"] the load, each as circuit.subcircuit describes
    them: a stage with the ports "in" and "out", the load with the port "in".
    Every output of the device gets its own copy of each stage and of the
    load. The models a stage or the load brings stand once in the netlist.
    The first stage of the k-th output (from 1) reads its node;
    ``out<k>`` is the output of its last stage and the input of its load. A
    chain without stages has the load on the output node of the device.
    Ground is node 0.

    electrodes : names of the electrodes the currents are induced on, in the
        order of the rows of currents. They have to be those the circuit has
        current sources for; its outputs may be others.
    dt : width of a time bin of the induced currents [s].
    currents : induced currents [A], shape (electrodes, bins), each value the
        mean current in its bin. A positive current flows through the source
        from the first to the second node the circuit gives for the electrode.
    circuit : DeviceCircuit.
    raw : file ngspice writes the voltages on the loads to.

    The run starts one bin before the first bin, with the circuit at rest and
    no current in that bin, and lasts to the end of the last bin, with the
    bin width as step.
    """
    currents = np.atleast_2d(np.asarray(currents, dtype=np.float64))
    sources = _current_sources(electrodes, dt, currents, circuit)

    lines, outputs = _chain(chain, circuit)
    lines.extend(sources)
    lines.extend(
        _transient(dt, currents.shape[1], raw, [f"v({node})" for node in outputs])
    )
    return "\n".join(lines) + "\n"


def solve(chain, electrodes, dt, currents, circuit):
    """Output voltages [V] on the bins of the induced currents, shape
    (outputs, bins), in the order of circuit.outputs. The arguments are those
    of write_netlist."""
    currents = np.atleast_2d(np.asarray(currents, dtype=np.float64))
    with tempfile.TemporaryDirectory() as folder:
        raw = Path(folder) / "out.raw"
        netlist = write_netlist(chain, electrodes, dt, currents, circuit, raw)
        return _run(netlist, raw, dt, currents.shape[1])


def write_short_circuit_netlist(electrodes, dt, currents, circuit, raw):
    """Netlist of one transient run of the device alone, with each of its
    outputs shorted to ground. electrodes, dt, currents and circuit are those of
    write_netlist; raw is the file ngspice writes the currents in the shorts
    to, in the order of circuit.outputs."""
    currents = np.atleast_2d(np.asarray(currents, dtype=np.float64))
    sources = _current_sources(electrodes, dt, currents, circuit)
    lines = ["device > short", *sources]
    shorts = []
    for k, output in enumerate(circuit.outputs.values(), start=1):
        lines.append(f"Vshort{k} {output} 0 0")
        shorts.append(f"i(Vshort{k})")
    lines.extend(circuit.lines)
    lines.extend(_transient(dt, currents.shape[1], raw, shorts))
    return "\n".join(lines) + "\n"


def short_circuit_currents(electrodes, dt, currents, circuit):
    """Currents [A] the device drives into a short at each of its outputs, on
    the bins of the induced currents, shape (outputs, bins), in the order of
    circuit.outputs. A positive current flows from the output node into the
    short."""
    currents = np.atleast_2d(np.asarray(currents, dtype=np.float64))
    with tempfile.TemporaryDirectory() as folder:
        raw = Path(folder) / "out.raw"
        netlist = write_short_circuit_netlist(electrodes, dt, currents, circuit, raw)
        return _run(netlist, raw, dt, currents.shape[1])


# frequencies per decade the output noise is calculated at
PER_DECADE = 50


def write_noise_netlist(chain, circuit, lowest_hz, highest_hz, raws):
    """Netlist of the noise analysis of some outputs. chain and circuit are
    those of write_netlist; raws are the files ngspice writes the spectra to,
    by the names of the outputs analysed."""
    lines, nodes = _chain(chain, circuit)
    node_of = dict(zip(circuit.outputs, nodes))
    # the analysis asks for a source, which leaves the noise at the output
    # as it is: the place of an induced current
    source_from, source_to = next(iter(circuit.sources.values()))
    lines.append(f"I1 {source_from} {source_to} dc 0 ac 1")
    control = [".control"]
    for k, (output, raw) in enumerate(raws.items(), 1):
        control.append(
            f"noise v({node_of[output]}) I1 dec {PER_DECADE} "
            f"{lowest_hz:.9g} {highest_hz:.9g}"
        )
        # every analysis leaves two plots: the spectra, then their integrals
        control.append(f"setplot noise{2 * k - 1}")
        control.append(f"wrdata {raw} onoise_spectrum")
    lines.extend([*control, ".endc", ".end"])
    return "\n".join(lines) + "\n"


def output_noise_spectrum(chain, circuit, lowest_hz, highest_hz, outputs=None):
    """Noise of the circuit at outputs, as ngspice calculates it from the
    thermal noise of the resistors and the noise of the device models, at
    27 degrees Celsius: the frequencies [Hz], from lowest_hz to highest_hz, and
    the amplitude spectral density at them [V / sqrt(Hz)], shape (outputs,
    frequencies). chain and circuit are those of write_netlist; the device and
    the load are part of the circuit.

    outputs : names of the outputs analysed, in the order of the spectra;
        None for all those of the circuit, in their order. The whole circuit
        is in each analysis, and each takes as long as the circuit is large.

    The noise of one output is taken by itself: what several outputs have in
    common is not given.
    """
    with tempfile.TemporaryDirectory() as folder:
        raws = {
            output: Path(folder) / f"noise{k}.raw"
            for k, output in enumerate(circuit.outputs if outputs is None else outputs)
        }
        netlist = Path(folder) / "noise.cir"
        netlist.write_text(
            write_noise_netlist(chain, circuit, lowest_hz, highest_hz, raws),
            encoding="utf-8",
        )
        subprocess.run(
            [_ngspice(), "-b", str(netlist)], check=True, capture_output=True, text=True
        )
        spectra = [np.loadtxt(raw, dtype=np.float64, ndmin=2) for raw in raws.values()]
    return spectra[0][:, 0], np.array([spectrum[:, 1] for spectrum in spectra])
