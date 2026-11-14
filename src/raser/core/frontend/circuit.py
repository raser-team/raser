"""Description of a stage: read from its SPICE file, written back as SPICE.

The description is what goes into run.json and what the scanned options
address: plain numbers under the names of the elements.
"""

import re
from pathlib import Path

# what an element is, by the quantity it carries: the letter SPICE knows it by
KINDS = {"ohm": "R", "farad": "C", "henry": "L", "volt": "V"}
QUANTITIES = {letter: quantity for quantity, letter in KINDS.items()}
# SPICE scale factors; "meg" has to be tried before "m"
SCALES = {
    "t": 1e12,
    "g": 1e9,
    "meg": 1e6,
    "k": 1e3,
    "m": 1e-3,
    "u": 1e-6,
    "n": 1e-9,
    "p": 1e-12,
    "f": 1e-15,
}
NUMBER = re.compile(r"([-+]?\d*\.?\d+(?:e[-+]?\d+)?)(meg|[tgkmunpf])?[a-z]*", re.I)


def spice_number(text):
    """Value of a SPICE number such as 3.3n, 1MEG, 47U, 3k or 2.25: the
    letters after the scale factor are a unit and carry no meaning."""
    match = NUMBER.fullmatch(text)
    if match is None:
        raise ValueError(f"{text!r} is not a SPICE number")
    scale = SCALES[match.group(2).lower()] if match.group(2) else 1.0
    return float(match.group(1)) * scale


def read_subcircuit(path):
    """Description, as subcircuit takes it, of the stage in a SPICE file.

    The stage is the subcircuit named like the file, with the nodes in, or in
    and out. Its elements may be resistors, capacitors, inductors, DC voltage
    sources and instances of other subcircuits; the SPICE name of an element
    is its designator. Everything else in the file, the other subcircuits and
    their models, goes into "models" as it is written.
    """
    path = Path(path)
    name = path.stem
    inside = False
    ports = None
    elements = {}
    models = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split(";")[0].strip()
        words = line.split()
        if not inside:
            if words[:2] and words[0].lower() == ".subckt" and words[1] == name:
                inside = True
                ports = words[2:]
            elif line and not line.startswith("*"):
                models.append(raw)
            continue
        if not line or line.startswith("*"):
            continue
        if words[0].lower() == ".ends":
            inside = False
            continue
        letter = words[0][0].upper()
        if letter == "X":
            elements[words[0]] = {"model": words[-1], "nodes": words[1:-1]}
        elif letter in QUANTITIES and len(words) >= 4:
            # a voltage source may say "dc" before its value
            elements[words[0]] = {
                "between": words[1:3],
                QUANTITIES[letter]: spice_number(words[-1]),
            }
        else:
            raise ValueError(f"Cannot read the element {line!r} of {path}")
    if ports is None or len(ports) not in (1, 2):
        raise ValueError(
            f"{path} has to hold .subckt {name} with the nodes in, or in and out"
        )
    description: dict = {
        "ports": dict(zip(("in", "out"), ports)),
        "elements": elements,
    }
    if models:
        description["models"] = models
    return description


def subcircuit(name, stage):
    """SPICE text of ``.subckt <name> <ports>``.

    stage["ports"] names the nodes the stage is reached by: "in", and "out"
    for a stage that has one. Ground is node "0".
    stage["elements"] holds the elements under their designators:
        {"between": [node, node], "ohm": R}       resistor [Ohm]
        {"between": [node, node], "farad": C}     capacitor [F]
        {"between": [node, node], "henry": L}     inductor [H]
        {"between": [plus, minus], "volt": V}     DC voltage source [V]
        {"model": subcircuit, "nodes": [...]}     an instance of a subcircuit
                                                  that stage["models"] holds

    stage["models"], SPICE lines of other subcircuits and models, is not part
    of the text: it stands once in the netlist, outside every subcircuit.
    """
    ports = stage["ports"]
    lines = [
        f".subckt {name} "
        + " ".join(ports[port] for port in ("in", "out") if port in ports)
    ]
    for designator, element in stage["elements"].items():
        if "model" in element:
            nodes = " ".join(element["nodes"])
            lines.append(f"X_{designator} {nodes} {element['model']}")
            continue
        quantities = [quantity for quantity in KINDS if quantity in element]
        if len(quantities) != 1:
            raise ValueError(
                f"Element {designator} of {name} has to carry one of "
                f"{list(KINDS)} or a model, not {sorted(element)}"
            )
        (quantity,) = quantities
        first, second = element["between"]
        lines.append(
            f"{KINDS[quantity]}_{designator} {first} {second} {element[quantity]:.9g}"
        )
    lines.append(f".ends {name}")
    return "\n".join(lines) + "\n"
