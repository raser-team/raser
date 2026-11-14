"""Write the SPICE subcircuit of a stage that a json file describes."""

# what an element is, by the quantity it carries: the letter SPICE knows it by
KINDS = {"ohm": "R", "farad": "C", "henry": "L", "volt": "V"}


def subcircuit(name, stage):
    """SPICE text of ``.subckt <name> <ports>``.

    stage["ports"] names the nodes the stage is reached by: "in", and "out"
    for a stage that has one. Ground is node "0".
    stage["elements"] holds the elements under their designators:
        {"between": [node, node], "ohm": R}       resistor [Ohm]
        {"between": [node, node], "farad": C}     capacitor [F]
        {"between": [node, node], "henry": L}     inductor [H]
        {"between": [plus, minus], "volt": V}     DC voltage source [V]
        {"model": subcircuit, "nodes": [...]}     a device model, as a
                                                  subcircuit given elsewhere
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
