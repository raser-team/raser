"""Circuit of a resistive layer with electrodes on it: the strips of a row,
or the pads of a grid, read out through the layer."""

from .device_circuit import DeviceCircuit


def resistive_row(
    rc_nodes,
    rc_node_width_m,
    length_m,
    sheet_resistance_ohm,
    capacitance_per_area_f_m2,
    strips,
    grounded=None,
    back="0",
):
    """DeviceCircuit of a resistive layer with strips in contact with it, the
    back of its depleted layer on the node `back`.

    The layer is cut across the strips into RC nodes of one width, each a
    node of the netlist with the capacitance of the depleted layer under it to
    the back; the layer between two neighbours is a resistor. The RC nodes
    under a strip are one node of the netlist, that of the strip, which is read
    out itself.

    rc_nodes : names of the RC nodes, in their order along the row. The current
        induced on an RC node flows into its node.
    rc_node_width_m : width of an RC node, across the strips [m].
    length_m : length of the strips and of the layer along them [m].
    sheet_resistance_ohm : resistance of a square of the layer [Ohm].
    capacitance_per_area_f_m2 : capacitance of the depleted layer per area
        [F / m^2].
    strips : for each strip, by its name, the numbers (from 0) of the first
        and of the last RC node under it.
    grounded : the same for each contact on the layer that is held on ground
        and not read out; none if not given.
    back : node at the back of the depleted layer, as planar_circuit takes
        it: ground "0", or "undepleted", shared with the undepleted layer.

    The layer ends open at both ends of the row. A positive current flows
    into the RC node.
    """
    rc_nodes = list(rc_nodes)
    if len(set(rc_nodes)) != len(rc_nodes):
        raise ValueError("Two RC nodes of the row have one name")
    node = [f"layer_{name}" for name in rc_nodes]
    for strip, (first, last) in strips.items():
        if not 0 <= first <= last < len(rc_nodes):
            raise ValueError(
                f"The strip {strip} lies on the RC nodes {first} to {last}, and "
                f"the row has the RC nodes 0 to {len(rc_nodes) - 1}"
            )
        for number in range(first, last + 1):
            if not node[number].startswith("layer_"):
                raise ValueError(f"Two strips lie on the RC node {rc_nodes[number]}")
            node[number] = f"{strip}_pad"
    for contact, (first, last) in (grounded or {}).items():
        if not 0 <= first <= last < len(rc_nodes):
            raise ValueError(
                f"The contact {contact} lies on the RC nodes {first} to {last}, and "
                f"the row has the RC nodes 0 to {len(rc_nodes) - 1}"
            )
        for number in range(first, last + 1):
            if not node[number].startswith("layer_"):
                raise ValueError(f"Two contacts lie on the RC node {rc_nodes[number]}")
            node[number] = "0"

    capacitance_f = capacitance_per_area_f_m2 * rc_node_width_m * length_m
    # from the middle of an RC node to the middle of the next one; a strip begins
    # at the edge of its first RC node, half an RC node from the middle of a neighbour
    square_ohm = sheet_resistance_ohm / length_m
    lines = []
    for number, name in enumerate(rc_nodes):
        if node[number] != "0":
            lines.append(f"Clayer_{name} {node[number]} {back} {capacitance_f:.9g}")
        if number + 1 == len(rc_nodes) or node[number] == node[number + 1]:
            continue
        on_strips = sum(
            not here.startswith("layer_") for here in node[number : number + 2]
        )
        width_m = rc_node_width_m * (1 - on_strips / 2)
        if width_m > 0:
            lines.append(
                f"Rlayer_{name} {node[number]} {node[number + 1]} "
                f"{square_ohm * width_m:.9g}"
            )
        else:
            raise ValueError(
                f"The strips on the RC nodes {name} and {rc_nodes[number + 1]} touch"
            )
    return DeviceCircuit(
        lines=tuple(lines),
        sources={name: (back, node[number]) for number, name in enumerate(rc_nodes)},
        outputs={strip: f"{strip}_pad" for strip in strips},
    )


def _inside(span, counts):
    """Refuse a span (x_first, x_last, y_first, y_last) not wholly on the
    RC nodes of the layer."""
    x_first, x_last, y_first, y_last = span
    if not (0 <= x_first <= x_last < counts[0] and 0 <= y_first <= y_last < counts[1]):
        raise ValueError(
            f"A contact lies on the RC nodes {x_first} to {x_last} by {y_first} to "
            f"{y_last}, and the layer has {counts[0]} by {counts[1]} RC nodes"
        )


def _on(node, spans, name, counts):
    """Give the RC nodes inside each span (x_first, x_last, y_first, y_last) the
    node `name`; an RC node may lie under one contact only."""
    for x_first, x_last, y_first, y_last in spans:
        _inside((x_first, x_last, y_first, y_last), counts)
        for i in range(x_first, x_last + 1):
            for j in range(y_first, y_last + 1):
                if not node[i][j].startswith("layer_"):
                    raise ValueError(f"Two contacts lie on the RC node {i}, {j}")
                node[i][j] = name


def resistive_grid(
    rc_nodes,
    counts,
    widths_m,
    sheet_resistance_ohm,
    capacitance_per_area_f_m2,
    pads,
    coupling_per_area_f_m2=None,
    grounded=None,
    back="0",
):
    """DeviceCircuit of a resistive layer cut into a grid of RC nodes, with pads
    that are read out, the back of its depleted layer on the node `back`.

    rc_nodes : names of the RC nodes; the RC node number i along x and j along y is
        rc_nodes[i * counts[1] + j]. The current induced on an RC node flows into
        its node.
    counts : numbers of RC nodes along x and along y.
    widths_m : widths of an RC node along x and along y [m].
    sheet_resistance_ohm : resistance of a square of the layer [Ohm].
    capacitance_per_area_f_m2 : capacitance of the depleted layer per area
        [F / m^2].
    pads : for each pad, by its name, the numbers (from 0) of its first and
        last RC node along x and of its first and last RC node along y.
    coupling_per_area_f_m2 : capacitance per area [F / m^2] between the layer
        and a pad that lies on a dielectric; the layer goes on under the pad.
        Not given, the pads are in contact with the layer, and the RC nodes
        under a pad are one node.
    grounded : for each contact on the layer that is held on ground and not
        read out, by its name, the list of its rectangles, each as a pad.
    back : node at the back of the depleted layer, as planar_circuit takes
        it: ground "0", or "undepleted", shared with the undepleted layer.

    The layer ends open at its four sides. A positive current flows into the
    RC node.
    """
    rc_nodes = list(rc_nodes)
    if len(rc_nodes) != counts[0] * counts[1] or len(set(rc_nodes)) != len(rc_nodes):
        raise ValueError(
            f"{len(set(rc_nodes))} names for the {counts[0]} by {counts[1]} RC nodes of the layer"
        )
    node = [
        [f"layer_{rc_nodes[i * counts[1] + j]}" for j in range(counts[1])]
        for i in range(counts[0])
    ]
    for spans in (grounded or {}).values():
        _on(node, spans, "0", counts)
    under = {}
    for pad, span in pads.items():
        if coupling_per_area_f_m2 is None:
            _on(node, [span], f"{pad}_pad", counts)
        else:
            _inside(span, counts)
            x_first, x_last, y_first, y_last = span
            for i in range(x_first, x_last + 1):
                for j in range(y_first, y_last + 1):
                    if (i, j) in under:
                        raise ValueError(f"Two pads lie over the RC node {i}, {j}")
                    under[i, j] = pad

    area_m2 = widths_m[0] * widths_m[1]
    lines = []
    for i in range(counts[0]):
        for j in range(counts[1]):
            name = rc_nodes[i * counts[1] + j]
            here = node[i][j]
            if here != "0":
                lines.append(
                    f"Clayer_{name} {here} {back} {capacitance_per_area_f_m2 * area_m2:.9g}"
                )
            if (i, j) in under:
                if here == "0":
                    raise ValueError(f"A pad lies over the grounded RC node {i}, {j}")
                lines.append(
                    f"Cpad_{name} {here} {under[i, j]}_pad "
                    f"{coupling_per_area_f_m2 * area_m2:.9g}"
                )
            # to the next RC node along x, then along y: squares in series
            for axis, (k, m) in enumerate(((i + 1, j), (i, j + 1))):
                if k == counts[0] or m == counts[1] or node[k][m] == here:
                    continue
                there = node[k][m]
                on_contacts = sum(not end.startswith("layer_") for end in (here, there))
                if on_contacts == 2:
                    raise ValueError(
                        f"The contacts on the RC nodes {i}, {j} and {k}, {m} touch"
                    )
                squares = widths_m[axis] / widths_m[1 - axis] * (1 - on_contacts / 2)
                lines.append(
                    f"R{'xy'[axis]}layer_{name} {here} {there} "
                    f"{sheet_resistance_ohm * squares:.9g}"
                )
    return DeviceCircuit(
        lines=tuple(lines),
        sources={
            rc_nodes[i * counts[1] + j]: (back, node[i][j])
            for i in range(counts[0])
            for j in range(counts[1])
        },
        outputs={pad: f"{pad}_pad" for pad in pads},
    )
