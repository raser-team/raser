"""The sensor in the SPICE netlist: a planar one with one read-out electrode, and several."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SensorCircuit:
    """The sensor as it stands in the netlist: once, for all electrodes.

    lines : SPICE lines of its elements. Ground is node 0.
    sources : for each electrode a current is induced on, by its name, the
        two nodes (from, to) of its induced current source.
    outputs : for each read-out, by its name, the node its first amplifier
        stage reads. The read-outs may be other than the electrodes of the
        currents: those of a resistive layer are its strips, the currents
        are those of its cells.

    The node names ``in<k>_<j>`` and ``out<k>`` belong to the stages.
    """

    lines: tuple[str, ...]
    sources: dict[str, tuple[str, str]]
    outputs: dict[str, str]


def undepleted_layer(
    area_m2, thickness_m, depleted_width_m, permittivity_f_per_m, resistivity_ohm_m
):
    """Resistance [Ohm] and capacitance [F] of the layer the bias does not
    deplete: a slab of the bulk between the depleted layer and the back.

    W. Riegler, NIM A 940 (2019) 453, arXiv:1812.07570, eq. 50.
    """
    if not 0 < depleted_width_m < thickness_m:
        raise ValueError(
            f"A depleted width of {depleted_width_m} m leaves no undepleted "
            f"layer in a sensor {thickness_m} m thick"
        )
    undepleted_m = thickness_m - depleted_width_m
    resistance_ohm = resistivity_ohm_m * undepleted_m / area_m2
    capacitance_f = permittivity_f_per_m * area_m2 / undepleted_m
    return resistance_ohm, capacitance_f


def planar_sensor(
    electrode,
    depleted_capacitance_f,
    undepleted=None,
    bias_resistance_ohm=None,
    coupling_capacitance_f=None,
):
    """SensorCircuit of a planar sensor with one read-out electrode, its back
    on ground.

    electrode : name of the read-out electrode.
    depleted_capacitance_f : capacitance of the depleted layer [F].
    undepleted : None for a fully depleted sensor, otherwise the resistance
        [Ohm] and the capacitance [F] of the undepleted layer, which lie in
        parallel between the depleted layer and the back.
    bias_resistance_ohm : resistance on the sensor from the electrode to its
        bias, which is ground for the signal [Ohm]. None: there is none.
    coupling_capacitance_f : capacitance on the sensor between the electrode
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
    if undepleted is None:
        back_of_depleted = "0"
        lines = [f"C{electrode}_depleted {pad} 0 {depleted_capacitance_f:.9g}"]
    else:
        resistance_ohm, capacitance_f = undepleted
        back_of_depleted = f"{electrode}_inner"
        lines = [
            f"C{electrode}_depleted {pad} {back_of_depleted} "
            f"{depleted_capacitance_f:.9g}",
            f"R{electrode}_undepleted {back_of_depleted} 0 {resistance_ohm:.9g}",
            f"C{electrode}_undepleted {back_of_depleted} 0 {capacitance_f:.9g}",
        ]
    if bias_resistance_ohm is not None:
        lines.append(f"R{electrode}_bias {pad} 0 {bias_resistance_ohm:.9g}")
    output = pad
    if coupling_capacitance_f is not None:
        output = f"{electrode}_port"
        lines.append(
            f"C{electrode}_coupling {pad} {output} {coupling_capacitance_f:.9g}"
        )
    return SensorCircuit(
        lines=tuple(lines),
        sources={electrode: (back_of_depleted, pad)},
        outputs={electrode: output},
    )


def side_by_side(sensors):
    """SensorCircuit of the electrodes of several sensors with nothing
    between them: the charge induced on one reaches no other."""
    lines: list[str] = []
    sources: dict = {}
    outputs: dict = {}
    for sensor in sensors:
        twice = sorted(set(sources) & set(sensor.sources))
        if twice:
            raise ValueError(f"The electrodes {twice} stand in two sensors")
        lines.extend(sensor.lines)
        sources.update(sensor.sources)
        outputs.update(sensor.outputs)
    return SensorCircuit(lines=tuple(lines), sources=sources, outputs=outputs)


def row_of_electrodes(sensors, between_f):
    """SensorCircuit of the electrodes of a row, each with the sensor it has
    by itself, and the capacitances between them.

    sensors : SensorCircuit of each electrode, one electrode each, in their
        order along the row.
    between_f : capacitance [F] between two electrodes of the row that are
        one, two, ... places apart. Electrodes further apart than it reaches
        have none between them.

    The capacitance lies between the electrodes themselves, before a coupling
    capacitance to the read-out.
    """
    row = side_by_side(sensors)
    electrodes = list(row.sources)
    if len(electrodes) != len(sensors):
        raise ValueError("Every sensor of a row has one electrode")
    lines = list(row.lines)
    for apart, farad in enumerate(between_f, start=1):
        for first, second in zip(electrodes, electrodes[apart:]):
            lines.append(
                f"C{first}_{second} {row.sources[first][1]} "
                f"{row.sources[second][1]} {farad:.9g}"
            )
    return SensorCircuit(lines=tuple(lines), sources=row.sources, outputs=row.outputs)
