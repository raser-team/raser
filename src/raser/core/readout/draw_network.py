"""Figures of the response of the network of a resistive layer to an impulse:
how the read-outs share it, their waveforms, and the circuit of the device."""

import tempfile
from pathlib import Path

import numpy as np

from raser.supports import figures

from . import schematic as schematic_module

# where the elements of the network are drawn, by the start of their names
HINTS = (
    (("Rxlayer_", "Rlayer_"), "right"),
    (("Rylayer_",), "up"),
    (("Clayer_",), "down"),
    (("Cpad_",), "up"),
)


def sharing(points_um, voltage, electrodes, dt, folder):
    """Draw how the read-outs share an impulse, as a function of its place,
    into folder/network_sharing.png, and return that path.

    points_um : the points of the impulses [um], shape (points, 2),
        (points, 1) or (points,); the x of each is the abscissa.
    voltage : output voltages [V], shape (points, outputs, bins).
    electrodes : names of the read-outs, in the order of the second axis of
        voltage.
    dt : width of a time bin [s].
    folder : where the figure is written.

    Left: the largest absolute value of the waveform of each read-out [mV].
    Right: the integral of the waveform [mV ns].
    """
    x_um = np.asarray(points_um, dtype=np.float64).reshape(len(voltage), -1)[:, 0]
    amplitude_mv = np.abs(voltage).max(axis=-1) / figures.UNIT["mV"]
    integral = voltage.sum(axis=-1) * dt / (figures.UNIT["mV"] * figures.UNIT["ns"])
    colors = figures.series(len(electrodes), ordered=False)
    figure, (left, right) = figures.new(1, 2)
    for number, name in enumerate(electrodes):
        left.plot(x_um, amplitude_mv[:, number], color=colors[number], label=name)
        right.plot(x_um, integral[:, number], color=colors[number])
    for axis in (left, right):
        axis.set_xlabel(figures.label("x of the impulse", "um"))
    left.set_ylabel(figures.label("Amplitude", "mV"))
    right.set_ylabel("Integral of the waveform [mV ns]")
    left.legend()
    return figures.save(figure, folder, "network_sharing")


def waveforms(voltage, electrodes, dt, folder):
    """Draw the waveforms of the read-outs for one impulse into
    folder/network_waveforms.png, and return that path.

    voltage : output voltages [V], shape (outputs, bins).
    electrodes : names of the read-outs, in the order of the first axis of
        voltage.
    dt : width of a time bin [s].
    folder : where the figure is written.

    The time axis reaches 1.5 times the last moment at which a read-out is
    above 1 % of the largest absolute voltage, at most the whole window; a
    window of zeros is drawn whole.
    """
    voltage = np.asarray(voltage, dtype=np.float64)
    bins = voltage.shape[-1]
    time_ns = (np.arange(bins) + 0.5) * dt / figures.UNIT["ns"]
    colors = figures.series(len(electrodes), ordered=False)
    figure, axis = figures.new()
    for number, name in enumerate(electrodes):
        axis.plot(
            time_ns,
            voltage[number] / figures.UNIT["mV"],
            color=colors[number],
            label=name,
        )
    peak = np.abs(voltage).max()
    limit_ns = time_ns[-1] + 0.5 * dt / figures.UNIT["ns"]
    if peak > 0:
        above = np.flatnonzero((np.abs(voltage) > 0.01 * peak).any(axis=0))
        limit_ns = min(1.5 * time_ns[above[-1]], limit_ns)
    axis.set_xlim(0, limit_ns)
    axis.set_xlabel(figures.label("Time", "ns"))
    axis.set_ylabel(figures.label("Amplitude", "mV"))
    axis.legend()
    return figures.save(figure, folder, "network_waveforms")


def _hint(line):
    name = line.split()[0]
    for starts, way in HINTS:
        if name.startswith(starts):
            return f"{line} ; {way}"
    return line


def schematic(circuit, folder):
    """Draw the circuit of a device into folder/network_schematic.png, and
    return that path.

    circuit : DeviceCircuit of a device with a resistive layer. The first two
        of its read-out nodes are the ports of the drawing, and the elements
        of the layer are laid out in rows, with their couplings above and
        below.
    folder : where the figure is written.
    """
    ports = list(circuit.outputs.values())[:2]
    lines = [f".subckt network {' '.join(ports)}"]
    lines += [_hint(line) for line in circuit.lines]
    lines.append(".ends")
    path = Path(folder) / "network_schematic.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as directory:
        cir_path = Path(directory) / "network.cir"
        cir_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        schematic_module.draw(cir_path, path)
    return path
