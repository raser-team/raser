"""Circuit of a planar sensor with one read-out electrode."""

from .spice import SensorCircuit


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


def planar_sensor(electrode, depleted_capacitance_f, undepleted=None):
    """SensorCircuit of a planar sensor read out DC-coupled on one electrode,
    its back on ground.

    electrode : name of the read-out electrode.
    depleted_capacitance_f : capacitance of the depleted layer [F].
    undepleted : None for a fully depleted sensor, otherwise the resistance
        [Ohm] and the capacitance [F] of the undepleted layer, which lie in
        parallel between the depleted layer and the back.

    The induced current is that of the depleted layer alone, with the
    undepleted layer taken as a conductor, and its source lies across the
    depleted layer. A positive current flows into the electrode.
    """
    pad = f"{electrode}_pad"
    if undepleted is None:
        return SensorCircuit(
            lines=(f"C{electrode}_depleted {pad} 0 {depleted_capacitance_f:.9g}",),
            sources={electrode: ("0", pad)},
            outputs={electrode: pad},
        )
    resistance_ohm, capacitance_f = undepleted
    inner = f"{electrode}_inner"
    return SensorCircuit(
        lines=(
            f"C{electrode}_depleted {pad} {inner} {depleted_capacitance_f:.9g}",
            f"R{electrode}_undepleted {inner} 0 {resistance_ohm:.9g}",
            f"C{electrode}_undepleted {inner} 0 {capacitance_f:.9g}",
        ),
        sources={electrode: (inner, pad)},
        outputs={electrode: pad},
    )
