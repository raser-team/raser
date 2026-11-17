"""Circuit of a resistive layer with electrodes on it: the strips of a row,
or the pads of a grid, read out through the layer."""

from .sensor_spice import SensorCircuit


def resistive_row(
    cells,
    cell_width_m,
    length_m,
    sheet_resistance_ohm,
    capacitance_per_area_f_m2,
    strips,
    grounded=None,
):
    """SensorCircuit of a resistive layer with strips in contact with it, the
    back of the sensor on ground.

    The layer is cut across the strips into cells of one width, each a node
    with the capacitance of the depleted layer under it to the back; the
    layer between two neighbours is a resistor. The cells under a strip are
    one node, that of the strip, which is read out itself.

    cells : names of the cells, in their order along the row. The current
        induced on a cell flows into its node.
    cell_width_m : width of a cell, across the strips [m].
    length_m : length of the strips and of the layer along them [m].
    sheet_resistance_ohm : resistance of a square of the layer [Ohm].
    capacitance_per_area_f_m2 : capacitance of the depleted layer per area
        [F / m^2].
    strips : for each strip, by its name, the numbers (from 0) of the first
        and of the last cell under it.
    grounded : the same for each contact on the layer that is held on ground
        and not read out; none if not given.

    The layer ends open at both ends of the row. A positive current flows
    into the cell.
    """
    cells = list(cells)
    if len(set(cells)) != len(cells):
        raise ValueError("Two cells of the row have one name")
    node = [f"layer_{name}" for name in cells]
    for strip, (first, last) in strips.items():
        if not 0 <= first <= last < len(cells):
            raise ValueError(
                f"The strip {strip} lies on the cells {first} to {last}, and "
                f"the row has the cells 0 to {len(cells) - 1}"
            )
        for number in range(first, last + 1):
            if not node[number].startswith("layer_"):
                raise ValueError(f"Two strips lie on the cell {cells[number]}")
            node[number] = f"{strip}_pad"
    for contact, (first, last) in (grounded or {}).items():
        if not 0 <= first <= last < len(cells):
            raise ValueError(
                f"The contact {contact} lies on the cells {first} to {last}, and "
                f"the row has the cells 0 to {len(cells) - 1}"
            )
        for number in range(first, last + 1):
            if not node[number].startswith("layer_"):
                raise ValueError(f"Two contacts lie on the cell {cells[number]}")
            node[number] = "0"

    capacitance_f = capacitance_per_area_f_m2 * cell_width_m * length_m
    # from the middle of a cell to the middle of the next one; a strip begins
    # at the edge of its first cell, half a cell from the middle of a neighbour
    square_ohm = sheet_resistance_ohm / length_m
    lines = []
    for number, name in enumerate(cells):
        if node[number] != "0":
            lines.append(f"Clayer_{name} {node[number]} 0 {capacitance_f:.9g}")
        if number + 1 == len(cells) or node[number] == node[number + 1]:
            continue
        on_strips = sum(
            not here.startswith("layer_") for here in node[number : number + 2]
        )
        width_m = cell_width_m * (1 - on_strips / 2)
        if width_m > 0:
            lines.append(
                f"Rlayer_{name} {node[number]} {node[number + 1]} "
                f"{square_ohm * width_m:.9g}"
            )
        else:
            raise ValueError(
                f"The strips on the cells {name} and {cells[number + 1]} touch"
            )
    return SensorCircuit(
        lines=tuple(lines),
        sources={name: ("0", node[number]) for number, name in enumerate(cells)},
        outputs={strip: f"{strip}_pad" for strip in strips},
    )


def _on(node, spans, name, counts):
    """Give the cells inside each span (x_first, x_last, y_first, y_last) the
    node `name`; a cell may lie under one contact only."""
    for x_first, x_last, y_first, y_last in spans:
        if not (
            0 <= x_first <= x_last < counts[0] and 0 <= y_first <= y_last < counts[1]
        ):
            raise ValueError(
                f"A contact lies on the cells {x_first} to {x_last} by {y_first} to "
                f"{y_last}, and the layer has {counts[0]} by {counts[1]} cells"
            )
        for i in range(x_first, x_last + 1):
            for j in range(y_first, y_last + 1):
                if not node[i][j].startswith("layer_"):
                    raise ValueError(f"Two contacts lie on the cell {i}, {j}")
                node[i][j] = name


def resistive_grid(
    cells,
    counts,
    widths_m,
    sheet_resistance_ohm,
    capacitance_per_area_f_m2,
    pads,
    coupling_per_area_f_m2=None,
    grounded=None,
):
    """SensorCircuit of a resistive layer cut into a grid of cells, with pads
    that are read out, the back of the sensor on ground.

    cells : names of the cells; the cell number i along x and j along y is
        cells[i * counts[1] + j]. The current induced on a cell flows into
        its node.
    counts : numbers of cells along x and along y.
    widths_m : widths of a cell along x and along y [m].
    sheet_resistance_ohm : resistance of a square of the layer [Ohm].
    capacitance_per_area_f_m2 : capacitance of the depleted layer per area
        [F / m^2].
    pads : for each pad, by its name, the numbers (from 0) of its first and
        last cell along x and of its first and last cell along y.
    coupling_per_area_f_m2 : capacitance per area [F / m^2] between the layer
        and a pad that lies on a dielectric; the layer goes on under the pad.
        Not given, the pads are in contact with the layer, and the cells
        under a pad are one node.
    grounded : for each contact on the layer that is held on ground and not
        read out, by its name, the list of its rectangles, each as a pad.

    The layer ends open at its four sides. A positive current flows into the
    cell.
    """
    cells = list(cells)
    if len(cells) != counts[0] * counts[1] or len(set(cells)) != len(cells):
        raise ValueError(
            f"{len(set(cells))} names for the {counts[0]} by {counts[1]} cells of the layer"
        )
    node = [
        [f"layer_{cells[i * counts[1] + j]}" for j in range(counts[1])]
        for i in range(counts[0])
    ]
    for spans in (grounded or {}).values():
        _on(node, spans, "0", counts)
    under = {}
    for pad, span in pads.items():
        if coupling_per_area_f_m2 is None:
            _on(node, [span], f"{pad}_pad", counts)
        else:
            x_first, x_last, y_first, y_last = span
            for i in range(x_first, x_last + 1):
                for j in range(y_first, y_last + 1):
                    if (i, j) in under:
                        raise ValueError(f"Two pads lie over the cell {i}, {j}")
                    under[i, j] = pad

    area_m2 = widths_m[0] * widths_m[1]
    lines = []
    for i in range(counts[0]):
        for j in range(counts[1]):
            name = cells[i * counts[1] + j]
            here = node[i][j]
            if here != "0":
                lines.append(
                    f"Clayer_{name} {here} 0 {capacitance_per_area_f_m2 * area_m2:.9g}"
                )
            if (i, j) in under:
                if here == "0":
                    raise ValueError(f"A pad lies over the grounded cell {i}, {j}")
                lines.append(
                    f"Cpad_{name} {here} {under[i, j]}_pad "
                    f"{coupling_per_area_f_m2 * area_m2:.9g}"
                )
            # to the next cell along x, then along y: squares in series
            for axis, (k, m) in enumerate(((i + 1, j), (i, j + 1))):
                if k == counts[0] or m == counts[1] or node[k][m] == here:
                    continue
                there = node[k][m]
                on_contacts = sum(not end.startswith("layer_") for end in (here, there))
                if on_contacts == 2:
                    raise ValueError(
                        f"The contacts on the cells {i}, {j} and {k}, {m} touch"
                    )
                squares = widths_m[axis] / widths_m[1 - axis] * (1 - on_contacts / 2)
                lines.append(
                    f"R{'xy'[axis]}layer_{name} {here} {there} "
                    f"{sheet_resistance_ohm * squares:.9g}"
                )
    return SensorCircuit(
        lines=tuple(lines),
        sources={
            cells[i * counts[1] + j]: ("0", node[i][j])
            for i in range(counts[0])
            for j in range(counts[1])
        },
        outputs={pad: f"{pad}_pad" for pad in pads},
    )
