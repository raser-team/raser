"""The circuit of a device in the SPICE netlist: a planar one with one read-out electrode, and several."""

from dataclasses import dataclass


@dataclass(frozen=True)
class DeviceCircuit:
    """The circuit of a device as it stands in the netlist: once, for all electrodes.

    lines : SPICE lines of its elements. Ground is node 0.
    sources : for each electrode a current is induced on, by its name, the
        two nodes (from, to) of its induced current source.
    outputs : for each read-out, by its name, the node its first amplifier
        stage reads. The read-outs may be other than the electrodes of the
        currents: those of a resistive layer are its strips, the currents
        are those of its RC nodes.
    alike : groups of outputs that have the same circuit behind each of
        them, so that their noise is the same: one noise spectrum, that of
        the middle output of the group, serves the whole group. An output in
        no group has a spectrum of its own.

    The node names ``in<k>_<j>`` and ``out<k>`` belong to the stages.
    """

    lines: tuple[str, ...]
    sources: dict[str, tuple[str, str]]
    outputs: dict[str, str]
    alike: tuple[tuple[str, ...], ...] = ()


def planar_circuit(
    electrode,
    depleted_capacitance_f,
    back="0",
    bias_resistance_ohm=None,
    coupling_capacitance_f=None,
):
    """DeviceCircuit of a planar device with one read-out electrode.

    electrode : name of the read-out electrode.
    depleted_capacitance_f : capacitance of the depleted layer [F].
    back : node at the back of the depleted layer: ground "0" for a fully
        depleted device, otherwise "undepleted", the one node all read-out
        electrodes share. The caller lays the resistance and the capacitance
        of the undepleted layer in parallel between it and ground.
    bias_resistance_ohm : resistance on the device from the electrode to its
        bias, which is ground for the signal [Ohm]. None: there is none.
    coupling_capacitance_f : capacitance on the device between the electrode
        and the read-out [F]. None: the electrode itself is read out. It
        needs the bias resistance, or the electrode has no DC potential.

    The induced current is that of the depleted layer alone, with the
    undepleted layer taken as a conductor, and its source lies across the
    depleted layer. A positive current flows into the electrode.
    """
    if coupling_capacitance_f is not None and bias_resistance_ohm is None:
        raise ValueError(
            "A coupling capacitance needs a bias resistance: without it the "
            "electrode has no DC potential"
        )
    pad = f"{electrode}_pad"
    lines = [f"C{electrode}_depleted {pad} {back} {depleted_capacitance_f:.9g}"]
    if bias_resistance_ohm is not None:
        lines.append(f"R{electrode}_bias {pad} 0 {bias_resistance_ohm:.9g}")
    output = pad
    if coupling_capacitance_f is not None:
        output = f"{electrode}_port"
        lines.append(
            f"C{electrode}_coupling {pad} {output} {coupling_capacitance_f:.9g}"
        )
    return DeviceCircuit(
        lines=tuple(lines),
        sources={electrode: (back, pad)},
        outputs={electrode: output},
    )


def side_by_side(circuits):
    """DeviceCircuit of the electrodes of several circuits with nothing
    between them: the charge induced on one reaches no other."""
    lines: list[str] = []
    sources: dict = {}
    outputs: dict = {}
    for circuit in circuits:
        twice = sorted(set(sources) & set(circuit.sources))
        if twice:
            raise ValueError(f"The electrodes {twice} stand in two circuits")
        lines.extend(circuit.lines)
        sources.update(circuit.sources)
        outputs.update(circuit.outputs)
    return DeviceCircuit(lines=tuple(lines), sources=sources, outputs=outputs)


def row_of_electrodes(circuits, between_f):
    """DeviceCircuit of the electrodes of a row, each with the circuit it has
    by itself, and the capacitances between them.

    circuits : DeviceCircuit of each electrode, one electrode each, in their
        order along the row.
    between_f : capacitance [F] between two electrodes of the row that are
        one, two, ... places apart. Electrodes further apart than it reaches
        have none between them.

    The capacitance lies between the electrodes themselves, before a coupling
    capacitance to the read-out.
    """
    row = side_by_side(circuits)
    electrodes = list(row.sources)
    if len(electrodes) != len(circuits):
        raise ValueError("Every circuit of a row has one electrode")
    lines = list(row.lines)
    for apart, farad in enumerate(between_f, start=1):
        for first, second in zip(electrodes, electrodes[apart:]):
            lines.append(
                f"C{first}_{second} {row.sources[first][1]} "
                f"{row.sources[second][1]} {farad:.9g}"
            )
    return DeviceCircuit(lines=tuple(lines), sources=row.sources, outputs=row.outputs)
