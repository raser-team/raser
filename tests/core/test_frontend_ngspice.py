from __future__ import annotations

import shutil

import pytest

from raser.core.frontend import CurrentSource
from raser.core.frontend import assemble_frontend
from raser.core.frontend import solve_frontend


pytestmark = [
    pytest.mark.ngspice,
    pytest.mark.skipif(shutil.which("ngspice") is None, reason="ngspice unavailable"),
]


def test_joint_sensor_and_afe_netlist_produces_an_output_waveform() -> None:
    source = CurrentSource(
        "readout",
        (-1.0e-9, 0.0, 1.0e-9, 2.0e-9),
        (0.0, 1.0e-6, 0.0, 0.0),
    )
    circuit = assemble_frontend(
        sources=(source,),
        sensor_values={"bulk_capacitance_pF": 2.5},
        afe={"input_resistance_ohm": 50.0, "voltage_gain": 10.0},
    )

    result = solve_frontend(circuit)

    assert result.unit == "V"
    assert result.times[0] == pytest.approx(source.times[0])
    assert result.times[-1] == pytest.approx(source.times[-1])
    assert max(map(abs, result.values["afe_out_0"])) > 0.0
