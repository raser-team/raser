from __future__ import annotations

import shutil

import pytest

from raser.core.frontend import CurrentSource
from raser.core.frontend import SheetContact
from raser.core.frontend import assemble_frontend
from raser.core.frontend import build_resistive_sheet_sensor
from raser.core.frontend import solve_frontend


def _sensor_network():
    return build_resistive_sheet_sensor(
        size_x_um=20.0,
        size_y_um=20.0,
        grid_x=3,
        grid_y=3,
        sheet_resistance_ohm_per_square=1000.0,
        backplane_capacitance_fF_per_node=10.0,
        coupling_capacitance_fF_per_contact=80.0,
        bias_resistance_ohm=1.0e6,
        bias_positions_um=((0.0, 0.0),),
        source_positions_um={"deposit": (10.0, 10.0)},
        contacts=(SheetContact("readout", ((10.0, 10.0),)),),
    )


def _two_output_sensor_network():
    return build_resistive_sheet_sensor(
        size_x_um=20.0,
        size_y_um=20.0,
        grid_x=3,
        grid_y=3,
        sheet_resistance_ohm_per_square=1000.0,
        backplane_capacitance_fF_per_node=10.0,
        coupling_capacitance_fF_per_contact=80.0,
        bias_resistance_ohm=1.0e6,
        bias_positions_um=((0.0, 0.0),),
        source_positions_um={"deposit": (10.0, 10.0)},
        contacts=(
            SheetContact("left", ((0.0, 10.0),)),
            SheetContact("right", ((20.0, 10.0),)),
        ),
    )


def test_resistive_sheet_exposes_source_and_afe_nodes() -> None:
    sensor = _sensor_network()

    assert sensor.source_nodes == {"deposit": "sheet_1_1"}
    assert sensor.output_nodes == {"readout": "sensor_out_readout"}
    assert sensor.netlist.count("Rsheet_x_") == 6
    assert sensor.netlist.count("Rsheet_y_") == 6
    assert sensor.netlist.count("Csheet_back_") == 9
    assert "Rin0 sensor_out_readout 0 50" not in sensor.netlist


def test_sensor_outputs_define_the_frontend_electrodes() -> None:
    source = CurrentSource("deposit", (0.0, 1.0e-9), (1.0e-6, 0.0))
    circuit = assemble_frontend(
        sources=(source,),
        sensor_values={},
        sensor_network=_two_output_sensor_network(),
        afe={"input_resistance_ohm": 50.0},
    )

    assert circuit.electrodes == ("left", "right")
    assert circuit.outputs == ("sensor_out_left", "sensor_out_right")
    assert "Rin0 sensor_out_left 0 50" in circuit.netlist
    assert "Rin1 sensor_out_right 0 50" in circuit.netlist


@pytest.mark.ngspice
@pytest.mark.skipif(shutil.which("ngspice") is None, reason="ngspice unavailable")
def test_resistive_sheet_and_afe_share_one_transient_solution() -> None:
    source = CurrentSource(
        "deposit",
        (0.0, 1.0e-10, 2.0e-10, 1.0e-9),
        (0.0, 1.0e-6, 0.0, 0.0),
    )
    circuit = assemble_frontend(
        sources=(source,),
        sensor_values={},
        sensor_network=_sensor_network(),
        afe={"input_resistance_ohm": 50.0, "voltage_gain": 10.0},
    )

    waveforms = solve_frontend(circuit)

    assert "Rin0 sensor_out_readout 0 50" in circuit.netlist
    assert max(map(abs, waveforms.values["afe_out_0"])) > 0.0
