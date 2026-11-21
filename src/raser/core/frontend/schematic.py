"""Schematic of a stage, drawn from its SPICE file.

The file says what is connected to what, and arrange tells from that where
each element is drawn. What cannot be told, or is wanted otherwise, stands
behind the element, after the ";" that SPICE reads as the start of a comment:

    x1 5 3 0 BFR840L3RHESD ; npn
    C2 4 5 3.3n  ; right 2, shift up 1

"right", "left", "up", "down" is the way from the first node of the element
to its second, over that many grid steps, 2 where none is given. "shift" moves
the whole element aside, a wire joining it to its nodes. "npn" is a transistor
with the nodes collector, base, emitter, its base on the left. "amp" is a
source that follows a voltage to ground, drawn as an amplifier from the node
it follows to its output.
"""

import math
from pathlib import Path

import matplotlib.pyplot as plt

from .circuit import read_subcircuit

WAYS = {"right": (1, 0), "left": (-1, 0), "up": (0, 1), "down": (0, -1)}
UNITS = {"ohm": "Ω", "farad": "F", "henry": "H", "volt": "V"}
PREFIXES = (
    (1e6, "M"),
    (1e3, "k"),
    (1.0, ""),
    (1e-3, "m"),
    (1e-6, "µ"),
    (1e-9, "n"),
    (1e-12, "p"),
)
GROUND = "0"
# where the collector and the emitter of a transistor are, seen from its base
COLLECTOR = (2, 1)
EMITTER = (2, -1)


def read_hints(path):
    """What stands behind the ";" of each element of the stage in a SPICE
    file, under the designator of the element."""
    path = Path(path)
    hints = {}
    inside = False
    for raw in path.read_text(encoding="utf-8").splitlines():
        words = raw.split(";")[0].split()
        if not words or words[0].startswith("*"):
            continue
        if words[0].lower() == ".subckt":
            inside = words[1] == path.stem
        elif words[0].lower() == ".ends":
            inside = False
        elif inside and ";" in raw:
            hints[words[0]] = raw.split(";", 1)[1].strip()
    return hints


def _step(words, designator):
    """(dx, dy) of "<way>" or "<way> <steps>"."""
    if not words or words[0] not in WAYS or len(words) > 2:
        raise ValueError(
            f"The drawing hint of {designator} has to say one of {list(WAYS)} and, "
            f"at most, over how many steps, not {' '.join(words)!r}"
        )
    steps = float(words[1]) if len(words) == 2 else 2.0
    return WAYS[words[0]][0] * steps, WAYS[words[0]][1] * steps


def _add(point, step):
    return point[0] + step[0], point[1] + step[1]


def _wire(start, end, along):
    """Points of the wire from the end of an element to its node: straight on
    the way the element goes, then the turn."""
    if start == end:
        return []
    if start[0] == end[0] or start[1] == end[1]:
        return [start, end]
    corner = (end[0], start[1]) if along[0] else (start[0], end[1])
    return [start, corner, end]


def layout(stage, hints):
    """Where the elements of a stage that have a hint are drawn, on a grid.

    Returns (nodes, placed): nodes gives the point (x, y) of each node, the
    input at (0, 0); placed gives, under each designator, "nodes", the nodes
    the element is drawn between, "ends", their points on the element, and
    "wires", the lines that join them to the points of their nodes. An end on
    ground has no wire: it carries its own ground sign.

    The elements are put down in the order of the hints, each once one of its
    nodes has a point; a node gets its point from the first element that
    reaches it.
    """
    elements = stage["elements"]
    unknown = [name for name in hints if name not in elements]
    if unknown:
        raise ValueError(f"The drawing hints {unknown} are of no element of the stage")
    nodes = {stage["ports"]["in"]: (0.0, 0.0)}
    placed: dict = {}
    while len(placed) < len(hints):
        before = len(placed)
        for name in hints:
            if name in placed:
                continue
            element = elements[name]
            parts = [part.split() for part in hints[name].split(",")]
            shift = (0.0, 0.0)
            for part in parts[1:]:
                if part[:1] != ["shift"]:
                    raise ValueError(
                        f"The drawing hint of {name} can only add a shift, "
                        f"not {' '.join(part)!r}"
                    )
                shift = _step(part[1:], name)
            if "model" in element:
                if parts[0] != ["npn"] or len(element["nodes"]) != 3:
                    raise ValueError(
                        f"{name}, an instance of {element['model']}, can only be "
                        "drawn as 'npn' with the nodes collector, base, emitter"
                    )
                collector, base, emitter = element["nodes"]
                if base not in nodes:
                    continue
                start = _add(nodes[base], shift)
                names = [base, collector, emitter]
                ends = [start, _add(start, COLLECTOR), _add(start, EMITTER)]
                ways = [(-1.0, 0.0), (0.0, 1.0), (0.0, -1.0)]
            else:
                if parts[0] == ["amp"]:
                    names = _amplifier(name, element)
                    step = (2.0, 0.0)
                else:
                    names = element["between"]
                    step = _step(parts[0], name)
                if names[0] in nodes:
                    start = _add(nodes[names[0]], shift)
                elif names[1] in nodes:
                    start = _add(
                        nodes[names[1]], (shift[0] - step[0], shift[1] - step[1])
                    )
                else:
                    continue
                ends = [start, _add(start, step)]
                ways = [(-step[0], -step[1]), step]
            wires = []
            for node, end, way in zip(names, ends, ways):
                if node == GROUND:
                    continue
                nodes.setdefault(node, end)
                wire = _wire(end, nodes[node], way)
                if wire:
                    wires.append(wire)
            placed[name] = {"nodes": names, "ends": ends, "wires": wires}
        if len(placed) == before:
            left = [name for name in hints if name not in placed]
            raise ValueError(
                f"The elements {left} hang on no node that the input reaches: "
                "they cannot be drawn"
            )
    return nodes, placed


def _amplifier(name, element):
    """[input, output] of a source drawn as an amplifier."""
    if (
        "gain" not in element
        or GROUND
        not in (
            element["follows"][1],
            element["between"][1],
        )
        or element["follows"][1] != element["between"][1]
    ):
        raise ValueError(
            f"{name} can only be drawn as 'amp' where it is a source that "
            "follows a voltage to ground and gives one to ground"
        )
    return [element["follows"][0], element["between"][0]]


def _lines(placed):
    """The level and upright lines that the placed elements take up, each
    with whether it is an element, a wire otherwise."""
    lines = []
    for place in placed.values():
        ends = place["ends"]
        if len(ends) == 3:
            lines.append((ends[0], (ends[1][0], ends[0][1]), True))
            lines.append((ends[1], ends[2], True))
        else:
            lines.append((ends[0], ends[1], True))
        for wire in place["wires"]:
            lines += [(first, last, False) for first, last in zip(wire[:-1], wire[1:])]
    return lines


def _taken(lines, start, end):
    """Whether the level or upright way from start to end runs along one of
    the lines, or across the sign in the middle of an element. Crossing a
    wire or the lead of an element is no hindrance."""
    along = 0 if start[1] == end[1] else 1
    across = 1 - along
    low, high = sorted((start[along], end[along]))
    for first, last, element in lines:
        if first[across] == last[across] == start[across]:
            # on the same line: taken where they share more than a point
            if min(high, max(first[along], last[along])) > max(
                low, min(first[along], last[along])
            ):
                return True
        elif element and first[along] == last[along]:
            # an element across: taken where the way meets its sign
            middle = (first[across] + last[across]) / 2
            if low < first[along] < high and abs(start[across] - middle) < 0.5:
                return True
    return False


def _main_path(stage, links):
    """The links from the input to the output that pass the most amplifying
    elements and, among those, the fewest others."""
    ports = stage["ports"]
    if "out" not in ports:
        return []
    best: list = []
    best_score = None

    def walk(node, path, seen):
        nonlocal best, best_score
        if node == ports["out"]:
            score = (sum(link[3] for link in path), -len(path))
            if best_score is None or score > best_score:
                best, best_score = list(path), score
            return
        for link in links:
            name, first, second, active = link
            if first == node:
                target = second
            elif second == node and not active:
                target = first
            else:
                continue
            if target in seen:
                continue
            walk(target, path + [(name, node, target, active)], seen | {target})

    walk(ports["in"], [], {ports["in"]})
    if best_score is None:
        raise ValueError("No way leads from the input of the stage to its output")
    return best


def arrange(stage, given=None):
    """Drawing hints of all elements of a stage, in the order layout is to
    put them down. given holds the hints the file itself has: they stand.

    The way from the input to the output runs to the right. Elements to
    ground hang down from their node, side by side. An element between two
    nodes that have a point runs level above what is already between them.
    The first element of any other branch goes up from the way, above all
    there is, and the branch runs on to the right.
    """
    given = given or {}
    elements = stage["elements"]
    links = []  # (designator, from, to, whether it amplifies)
    grounded: dict = {}
    for name, element in elements.items():
        if "model" in element:
            if name not in given:
                raise ValueError(
                    f"What {name}, an instance of {element['model']}, is cannot be "
                    "told from its nodes: say it behind the element, as in '; npn'"
                )
            collector, base, _ = element["nodes"]
            links.append((name, base, collector, True))
        elif "gain" in element:
            links.append((name, *_amplifier(name, element), True))
        elif GROUND in element["between"]:
            (node,) = [node for node in element["between"] if node != GROUND]
            grounded.setdefault(node, []).append(name)
        else:
            links.append((name, *element["between"], False))
    path = _main_path(stage, links)
    on_path = {stage["ports"]["in"]} | {link[2] for link in path}
    path_names = {link[0] for link in path}
    # the branches: elements off the way that share a node off the way
    branch: dict = {}
    for name, first, second, _ in links:
        if name not in path_names:
            for node in (first, second):
                if node not in on_path:
                    branch.setdefault(node, node)
    for name, first, second, _ in links:
        if name not in path_names and first in branch and second in branch:
            old, new = branch[first], branch[second]
            branch = {
                node: new if root == old else root for node, root in branch.items()
            }
    touching: dict = {}
    for name, first, second, _ in links:
        if name not in path_names:
            for here, there in ((first, second), (second, first)):
                if here in on_path and there in branch:
                    touching.setdefault(here, set()).add(branch[there])

    def room(node):
        # steps to the right that what hangs on a node takes up
        beside = max(len(grounded.get(node, ())), len(touching.get(node, ())))
        return 2 * max(beside - 1, 0)

    hints: dict = {}
    nodes, placed = layout(stage, hints)

    def put(name, hint):
        nonlocal nodes, placed
        hints[name] = given.get(name, hint)
        nodes, placed = layout(stage, hints)

    def shifted(hint, way, steps):
        return f"{hint}, shift {way} {steps:g}" if steps else hint

    for name, first, _, _ in path:
        element = elements[name]
        if "model" in element:
            hint = given[name]
        elif "gain" in element:
            hint = "amp"
        else:
            hint = "right" if element["between"][0] == first else "left"
        put(name, shifted(hint, "right", room(first)))
    while len(hints) < len(elements):
        before = len(hints)
        for name, element in elements.items():
            if name in hints:
                continue
            if "model" in element or "gain" in element:
                continue
            first, second = element["between"]
            known = [node for node in (first, second) if node in nodes]
            if not known:
                continue
            if name in given:
                put(name, given[name])
            elif GROUND in (first, second):
                beside = sum(other in hints for other in grounded[known[0]])
                put(
                    name,
                    shifted("down" if second == GROUND else "up", "right", 2 * beside),
                )
            elif len(known) == 2:
                start, end = nodes[first], nodes[second]
                along = 0 if start[0] != end[0] else 1
                reach = end[along] - start[along]
                way = (("left", "right"), ("down", "up"))[along][reach > 0]
                aside = 0.0
                step = (0.0, 1.5) if along == 0 else (1.5, 0.0)
                lines = _lines(placed)
                while _taken(
                    lines,
                    (
                        start[0] + aside * step[0] / 1.5,
                        start[1] + aside * step[1] / 1.5,
                    ),
                    (
                        start[0] + aside * step[0] / 1.5 + (reach if along == 0 else 0),
                        start[1] + aside * step[1] / 1.5 + (reach if along == 1 else 0),
                    ),
                ):
                    aside += 1.5
                put(
                    name,
                    shifted(
                        f"{way} {abs(reach):g}", "up" if along == 0 else "right", aside
                    ),
                )
            elif known[0] in on_path:
                here = nodes[known[0]]
                lines = _lines(placed)
                top = math.ceil(max(max(line[0][1], line[1][1]) for line in lines)) + 1
                aside = 0
                while _taken(lines, (here[0] + aside, here[1]), (here[0] + aside, top)):
                    aside += 1
                if aside > room(known[0]):
                    raise ValueError(
                        f"There is no free place for {name} to go up from the node "
                        f"{known[0]}: say behind it where to draw it"
                    )
                way = "up" if first == known[0] else "down"
                put(name, shifted(f"{way} {top - here[1]:g}", "right", aside))
            else:
                way = "right" if first == known[0] else "left"
                put(name, shifted(way, "right", room(known[0])))
        if len(hints) == before:
            left = [name for name in elements if name not in hints]
            raise ValueError(
                f"Where to draw the elements {left} cannot be told from the "
                "stage: say it behind them"
            )
    return hints


def value_text(element):
    """Value of an element as a schematic carries it: 3.3 nF, 475 Ω, × -3000."""
    if "gain" in element:
        return f"× {element['gain']:g}"
    if "model" in element:
        return element["model"]
    (quantity,) = [quantity for quantity in UNITS if quantity in element]
    value = element[quantity]
    # the largest prefix the value reaches, the smallest one below them all
    scale, prefix = next(
        (pair for pair in PREFIXES if abs(value) >= pair[0] * (1 - 1e-9)), PREFIXES[-1]
    )
    text = f"{value / scale:.4g} {prefix}{UNITS[quantity]}"
    return f"{text}\nno noise" if element.get("noiseless") else text


def _symbol(axis, element, start, end):
    """Two-terminal element between two points: leads, and its sign in the
    middle, half a step long."""
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = (dx**2 + dy**2) ** 0.5
    ux, uy = dx / length, dy / length
    px, py = -uy, ux
    mid = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)

    def at(along, across):
        return mid[0] + along * ux + across * px, mid[1] + along * uy + across * py

    def line(*points, **style):
        xs, ys = zip(*points)
        axis.plot(xs, ys, color="black", lw=style.get("lw", 1.2), solid_capstyle="butt")

    half = 0.35
    if "farad" in element:
        line(start, at(-0.08, 0))
        line(at(0.08, 0), end)
        line(at(-0.08, -0.3), at(-0.08, 0.3), lw=1.8)
        line(at(0.08, -0.3), at(0.08, 0.3), lw=1.8)
        return
    line(start, at(-half, 0))
    line(at(half, 0), end)
    if "ohm" in element:
        line(
            at(-half, -0.13),
            at(half, -0.13),
            at(half, 0.13),
            at(-half, 0.13),
            at(-half, -0.13),
        )
    elif "henry" in element:
        radius = half / 4
        for hump in range(4):
            centre = -half + (2 * hump + 1) * radius
            line(
                *[
                    at(
                        centre + radius * math.cos(math.pi * k / 12),
                        1.6 * radius * math.sin(math.pi * k / 12),
                    )
                    for k in range(13)
                ]
            )
    else:
        # a source: a circle, "+" towards the first node of a DC source
        line(
            *[
                at(
                    half * math.cos(math.pi * k / 12),
                    half * math.sin(math.pi * k / 12),
                )
                for k in range(25)
            ]
        )
        if "volt" in element:
            axis.text(*at(-0.15, 0), "+", ha="center", va="center", fontsize=8)


def _between(point, first, last):
    """Whether point lies on the upright or level line from first to last."""
    for along, across in ((0, 1), (1, 0)):
        if point[across] == first[across] == last[across]:
            return (
                min(first[along], last[along])
                < point[along]
                < max(first[along], last[along])
            )
    return False


def _ground(axis, point, way):
    px, py = -way[1], way[0]
    for along, width in ((0.0, 0.28), (0.09, 0.18), (0.18, 0.08)):
        x, y = point[0] + along * way[0], point[1] + along * way[1]
        axis.plot(
            [x - width * px, x + width * px],
            [y - width * py, y + width * py],
            color="black",
            lw=1.2,
        )


def _triangle(axis, start, end):
    """Amplifier from its input to its output, to the right."""
    y = start[1]
    left, right = start[0] + 0.5, end[0] - 0.5
    axis.plot([start[0], left], [y, y], color="black", lw=1.2)
    axis.plot([right, end[0]], [y, y], color="black", lw=1.2)
    axis.plot(
        [left, left, right, left],
        [y - 0.55, y + 0.55, y, y - 0.55],
        color="black",
        lw=1.2,
    )


def _npn(axis, base, collector, emitter):
    bar_x = base[0] + 1.3
    axis.plot([base[0], bar_x], [base[1], base[1]], color="black", lw=1.2)
    axis.plot([bar_x, bar_x], [base[1] - 0.4, base[1] + 0.4], color="black", lw=2.2)
    for end, side in ((collector, 1), (emitter, -1)):
        knee = (end[0], base[1] + side * 0.6)
        axis.plot(
            [bar_x, knee[0], end[0]],
            [base[1] + side * 0.15, knee[1], end[1]],
            color="black",
            lw=1.2,
        )
    axis.annotate(
        "",
        xy=(emitter[0], base[1] - 0.6),
        xytext=(bar_x, base[1] - 0.15),
        arrowprops={"arrowstyle": "-|>", "color": "black", "lw": 1.2},
    )


def draw(path, figure_path):
    """Draw the schematic of the stage in the SPICE file path into figure_path."""
    path = Path(path)
    stage = read_subcircuit(path)
    nodes, placed = layout(stage, arrange(stage, read_hints(path)))
    figure, axis = plt.subplots()
    segments = []
    for name, place in placed.items():
        element = stage["elements"][name]
        ends = place["ends"]
        if "model" in element:
            _npn(axis, *ends)
            label_at = (ends[0][0] + 2.15, ends[0][1])
            aligned = ("left", "center")
            ways = [(-1.0, 0.0), (0.0, 1.0), (0.0, -1.0)]
            segments += [(end, end) for end in ends]
        else:
            if place["nodes"] == element["between"]:
                _symbol(axis, element, *ends)
            else:
                _triangle(axis, *ends)
            mid = ((ends[0][0] + ends[1][0]) / 2, (ends[0][1] + ends[1][1]) / 2)
            upright = ends[0][0] == ends[1][0]
            label_at = (mid[0] + 0.45, mid[1]) if upright else (mid[0], mid[1] + 0.42)
            aligned = ("left", "center") if upright else ("center", "bottom")
            if place["nodes"] != element["between"]:
                label_at = (mid[0], mid[1] + 0.7)
            step = (ends[1][0] - ends[0][0], ends[1][1] - ends[0][1])
            size = max(abs(step[0]), abs(step[1]))
            ways = [
                (-step[0] / size, -step[1] / size),
                (step[0] / size, step[1] / size),
            ]
            segments.append((ends[0], ends[1]))
        axis.text(
            *label_at,
            f"{name}\n{value_text(element)}",
            fontsize=8,
            ha=aligned[0],
            va=aligned[1],
        )
        for node, end, way in zip(place["nodes"], ends, ways):
            if node == GROUND:
                _ground(axis, end, way)
        for wire in place["wires"]:
            xs, ys = zip(*wire)
            axis.plot(xs, ys, color="black", lw=1.2)
            segments += list(zip(wire[:-1], wire[1:]))
    # a dot where three lines meet: ends count once, a line passing through twice
    for point in {end for segment in segments for end in segment}:
        meeting = 0
        for first, last in segments:
            if point in (first, last):
                meeting += 1
            elif _between(point, first, last):
                meeting += 2
        if meeting > 2:
            axis.plot(*point, "o", color="black", ms=3.5, zorder=3)
    for port, node in stage["ports"].items():
        x, y = nodes[node]
        axis.plot(x, y, "o", color="white", mec="black", ms=6, zorder=3)
        axis.text(x, y + 0.3, port, ha="center", va="bottom", fontsize=9, weight="bold")
    axis.set_aspect("equal")
    axis.axis("off")
    axis.margins(0.08)
    width = axis.get_xlim()[1] - axis.get_xlim()[0]
    height = axis.get_ylim()[1] - axis.get_ylim()[0]
    figure.set_size_inches(0.75 * width + 1, 0.75 * height + 1)
    axis.set_title(path.stem, fontsize=11, pad=30)
    figure.savefig(figure_path, dpi=160, bbox_inches="tight")
    plt.close(figure)
