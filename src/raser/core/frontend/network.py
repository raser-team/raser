"""Sensor and AFE circuit assembly."""

from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from .sensor_network import SensorNetwork


@dataclass(frozen=True)
class CurrentSource:
    electrode: str
    times: tuple[float, ...]
    currents: tuple[float, ...]

    def __post_init__(self) -> None:
        if len(self.times) != len(self.currents):
            raise ValueError(
                "Frontend source times and currents must have equal length"
            )
        if len(self.times) < 2:
            raise ValueError("Frontend source requires at least two samples")
        if any(right <= left for left, right in zip(self.times, self.times[1:])):
            raise ValueError("Frontend source times must increase")


@dataclass(frozen=True)
class FrontendCircuit:
    electrodes: tuple[str, ...]
    netlist: str
    outputs: tuple[str, ...]
    sensor_values: Mapping[str, Any]
    afe: Mapping[str, Any]
    times: tuple[float, ...]


@dataclass(frozen=True)
class FrontendWaveforms:
    times: tuple[float, ...]
    values: Mapping[str, tuple[float, ...]]
    unit: str = "V"


def _pwl(source: CurrentSource, origin: float) -> str:
    values = " ".join(
        f"{time - origin:.12g} {current:.12g}"
        for time, current in zip(source.times, source.currents)
    )
    return f"PWL({values})"


def assemble_frontend(
    *,
    sources: Sequence[CurrentSource],
    sensor_values: Mapping[str, Any],
    afe: Mapping[str, Any],
    sensor_network: SensorNetwork | None = None,
) -> FrontendCircuit:
    if not sources:
        raise ValueError("Frontend requires electrode current sources")
    electrodes = tuple(source.electrode for source in sources)
    if len(set(electrodes)) != len(electrodes):
        raise ValueError("Frontend electrode names must be unique")
    times = tuple(sources[0].times)
    if any(tuple(source.times) != times for source in sources[1:]):
        raise ValueError("Frontend sources must share one time axis")
    origin = times[0]

    if sensor_network is not None:
        missing_sources = set(electrodes) - set(sensor_network.source_nodes)
        if missing_sources:
            raise ValueError(
                "Sensor network has no nodes for: " + ", ".join(sorted(missing_sources))
            )
        duplicated_values = {
            "bulk_capacitance_pF",
            "interelectrode_capacitance_pF",
            "bias_resistance_ohm",
            "ac_coupling_capacitance_pF",
        } & set(sensor_values)
        if duplicated_values:
            raise ValueError(
                "Sensor network duplicates lumped values: "
                + ", ".join(sorted(duplicated_values))
            )

    lines = ["* RASER sensor and frontend"]
    for index, source in enumerate(sources):
        source_node = (
            sensor_network.source_nodes[source.electrode]
            if sensor_network is not None
            else source.electrode
        )
        lines.append(f"I{index} {source_node} 0 {_pwl(source, origin)}")

    if sensor_network is not None:
        lines.append(sensor_network.netlist.rstrip())

    bulk_capacitance = sensor_values.get("bulk_capacitance_pF")
    if bulk_capacitance is not None:
        lines.append("Vbackplane backplane 0 0")
        for index, electrode in enumerate(electrodes):
            lines.append(
                f"Cbulk{index} {electrode} backplane {float(bulk_capacitance):.12g}p"
            )

    coupling = sensor_values.get("interelectrode_capacitance_pF")
    if coupling is not None:
        for index, (left, right) in enumerate(zip(electrodes, electrodes[1:])):
            lines.append(f"Ccouple{index} {left} {right} {float(coupling):.12g}p")

    bias_resistance = sensor_values.get("bias_resistance_ohm")
    if bias_resistance is not None:
        lines.append("Vbias bias 0 0")
        for index, electrode in enumerate(electrodes):
            lines.append(f"Rbias{index} {electrode} bias {float(bias_resistance):.12g}")

    ac_coupling = sensor_values.get("ac_coupling_capacitance_pF")
    input_resistance = afe.get("input_resistance_ohm", afe.get("Broad_Band_Imp"))
    voltage_gain = afe.get("voltage_gain", afe.get("Broad_Band_Gain"))
    outputs = []
    sensor_outputs = (
        tuple(sensor_network.output_nodes.items())
        if sensor_network is not None
        else tuple((electrode, electrode) for electrode in electrodes)
    )
    for index, (electrode, sensor_node) in enumerate(sensor_outputs):
        input_node = sensor_node if sensor_network is not None else f"afe_in_{index}"
        output_node = f"afe_out_{index}"
        if sensor_network is None:
            if ac_coupling is not None:
                lines.append(
                    f"Cac{index} {electrode} {input_node} {float(ac_coupling):.12g}p"
                )
            else:
                lines.append(f"Rconnect{index} {electrode} {input_node} 1u")
        if input_resistance is not None:
            lines.append(f"Rin{index} {input_node} 0 {float(input_resistance):.12g}")
        if voltage_gain is None:
            outputs.append(input_node)
        else:
            lines.append(
                f"Eafe{index} {output_node} 0 {input_node} 0 {float(voltage_gain):.12g}"
            )
            outputs.append(output_node)

    circuit = afe.get("netlist")
    if circuit is not None:
        lines.append(str(circuit).rstrip())

    lines.append(".end")
    return FrontendCircuit(
        electrodes=tuple(electrode for electrode, _ in sensor_outputs),
        netlist="\n".join(lines) + "\n",
        outputs=tuple(outputs),
        sensor_values=dict(sensor_values),
        afe=dict(afe),
        times=times,
    )


def solve_frontend(
    circuit: FrontendCircuit,
    *,
    executable: str = "ngspice",
) -> FrontendWaveforms:
    step = min(right - left for left, right in zip(circuit.times, circuit.times[1:]))
    stop = circuit.times[-1] - circuit.times[0]
    if stop <= 0:
        raise ValueError("Frontend transient duration must be positive")

    with tempfile.TemporaryDirectory(prefix="raser-frontend-") as temporary:
        directory = Path(temporary)
        control = [".control", f"tran {step:.12g} {stop:.12g}"]
        output_paths = []
        for index, output in enumerate(circuit.outputs):
            path = directory / f"waveform_{index}.dat"
            output_paths.append(path)
            control.append(f"wrdata {path} v({output})")
        control.extend(("quit", ".endc", ".end"))
        netlist = circuit.netlist.removesuffix(".end\n") + "\n".join(control) + "\n"
        netlist_path = directory / "frontend.cir"
        netlist_path.write_text(netlist, encoding="utf-8")
        subprocess.run(
            [executable, "-b", str(netlist_path)],
            cwd=directory,
            check=True,
            capture_output=True,
            text=True,
        )

        values: dict[str, tuple[float, ...]] = {}
        output_times: tuple[float, ...] | None = None
        for output, path in zip(circuit.outputs, output_paths):
            data = np.atleast_2d(np.loadtxt(path, dtype=np.float64))
            if data.shape[1] < 2:
                raise ValueError(f"ngspice waveform has fewer than two columns: {path}")
            times = tuple(float(value + circuit.times[0]) for value in data[:, 0])
            if output_times is None:
                output_times = times
            elif times != output_times:
                raise ValueError("ngspice outputs have different time axes")
            values[output] = tuple(float(value) for value in data[:, -1])

    return FrontendWaveforms(output_times or (), values)
