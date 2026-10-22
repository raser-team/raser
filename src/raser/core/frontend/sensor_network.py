"""Sensor-network fragments for joint Frontend circuit solutions."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping, Sequence


_SPICE_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class SensorNetwork:
    netlist: str
    source_nodes: Mapping[str, str]
    output_nodes: Mapping[str, str]

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_nodes", dict(self.source_nodes))
        object.__setattr__(self, "output_nodes", dict(self.output_nodes))
        if not self.source_nodes or not self.output_nodes:
            raise ValueError("Sensor network requires source and output nodes")
        names = (
            tuple(self.source_nodes)
            + tuple(self.source_nodes.values())
            + tuple(self.output_nodes)
            + tuple(self.output_nodes.values())
        )
        if any(_SPICE_NAME.fullmatch(name) is None for name in names):
            raise ValueError("Sensor network names must be SPICE identifiers")
        if len(set(self.output_nodes.values())) != len(self.output_nodes):
            raise ValueError("Sensor network output nodes must be unique")


@dataclass(frozen=True)
class SheetContact:
    name: str
    positions_um: tuple[tuple[float, float], ...]

    def __post_init__(self) -> None:
        if _SPICE_NAME.fullmatch(self.name) is None:
            raise ValueError("Sheet contact name must be a SPICE identifier")
        if not self.positions_um:
            raise ValueError("Sheet contact requires at least one position")


def build_resistive_sheet_sensor(
    *,
    size_x_um: float,
    size_y_um: float,
    grid_x: int,
    grid_y: int,
    sheet_resistance_ohm_per_square: float,
    backplane_capacitance_fF_per_node: float,
    coupling_capacitance_fF_per_contact: float,
    bias_resistance_ohm: float,
    bias_positions_um: Sequence[tuple[float, float]],
    source_positions_um: Mapping[str, tuple[float, float]],
    contacts: Sequence[SheetContact],
    coupling: str = "ac",
) -> SensorNetwork:
    """Generate a resistive-sheet sensor fragment for Frontend."""
    if size_x_um <= 0.0 or size_y_um <= 0.0:
        raise ValueError("Resistive-sheet dimensions must be positive")
    if grid_x < 2 or grid_y < 2:
        raise ValueError("Resistive-sheet grids require two nodes per axis")
    positive_values = (
        sheet_resistance_ohm_per_square,
        backplane_capacitance_fF_per_node,
        coupling_capacitance_fF_per_contact,
        bias_resistance_ohm,
    )
    if any(value <= 0.0 for value in positive_values):
        raise ValueError("Resistive-sheet electrical values must be positive")
    if coupling not in {"ac", "dc"}:
        raise ValueError("Sheet coupling must be ac or dc")
    if not bias_positions_um or not source_positions_um or not contacts:
        raise ValueError("Sheet bias, sources, and contacts require positions")

    step_x = size_x_um / (grid_x - 1)
    step_y = size_y_um / (grid_y - 1)

    def node_name(column: int, row: int) -> str:
        return f"sheet_{column}_{row}"

    def nearest(position: tuple[float, float]) -> tuple[int, int]:
        x_um, y_um = map(float, position)
        if not 0.0 <= x_um <= size_x_um or not 0.0 <= y_um <= size_y_um:
            raise ValueError(f"Sheet position lies outside its domain: {position}")
        return (
            min(grid_x - 1, max(0, round(x_um / step_x))),
            min(grid_y - 1, max(0, round(y_um / step_y))),
        )

    source_nodes: dict[str, str] = {}
    for name, position in source_positions_um.items():
        if _SPICE_NAME.fullmatch(name) is None:
            raise ValueError("Sheet source name must be a SPICE identifier")
        source_nodes[name] = node_name(*nearest(position))

    lines = ["* RASER resistive sensor sheet", "Vsheet_backplane sheet_backplane 0 0"]
    for row in range(grid_y):
        for column in range(grid_x):
            node = node_name(column, row)
            index = row * grid_x + column
            lines.append(
                f"Csheet_back_{index} {node} sheet_backplane "
                f"{backplane_capacitance_fF_per_node:.12g}f"
            )
            if column + 1 < grid_x:
                resistance = sheet_resistance_ohm_per_square * step_x / step_y
                lines.append(
                    f"Rsheet_x_{index} {node} {node_name(column + 1, row)} "
                    f"{resistance:.12g}"
                )
            if row + 1 < grid_y:
                resistance = sheet_resistance_ohm_per_square * step_y / step_x
                lines.append(
                    f"Rsheet_y_{index} {node} {node_name(column, row + 1)} "
                    f"{resistance:.12g}"
                )

    lines.append("Vsheet_bias sheet_bias 0 0")
    bias_nodes = sorted({nearest(position) for position in bias_positions_um})
    resistance_per_node = bias_resistance_ohm * len(bias_nodes)
    for index, coordinates in enumerate(bias_nodes):
        lines.append(
            f"Rsheet_bias_{index} {node_name(*coordinates)} sheet_bias "
            f"{resistance_per_node:.12g}"
        )

    output_nodes: dict[str, str] = {}
    for contact_index, contact in enumerate(contacts):
        if contact.name in output_nodes:
            raise ValueError(f"Duplicate sheet contact: {contact.name}")
        output = f"sensor_out_{contact.name}"
        output_nodes[contact.name] = output
        contact_nodes = sorted({nearest(position) for position in contact.positions_um})
        for node_index, coordinates in enumerate(contact_nodes):
            sheet_node = node_name(*coordinates)
            element = f"{contact_index}_{node_index}"
            if coupling == "ac":
                capacitance = coupling_capacitance_fF_per_contact / len(contact_nodes)
                lines.append(
                    f"Csheet_contact_{element} {sheet_node} {output} "
                    f"{capacitance:.12g}f"
                )
            else:
                lines.append(f"Rsheet_contact_{element} {sheet_node} {output} 1u")

    return SensorNetwork(
        netlist="\n".join(lines) + "\n",
        source_nodes=source_nodes,
        output_nodes=output_nodes,
    )
