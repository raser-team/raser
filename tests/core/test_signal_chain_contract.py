from __future__ import annotations

import pytest

from raser.core.frontend import CurrentSource
from raser.core.frontend import assemble_frontend


def test_current_frontend_and_metrics_share_one_waveform_contract() -> None:
    times = (0.5, 2.0)
    values = {"left": (1.0, 0.5), "right": (-1.0, -0.5)}

    sources = tuple(
        CurrentSource(electrode, times, samples)
        for electrode, samples in values.items()
    )
    circuit = assemble_frontend(
        sources=sources,
        sensor_values={
            "bulk_capacitance_pF": 2.5,
            "interelectrode_capacitance_pF": 0.2,
            "bias_resistance_ohm": 1.0e6,
            "ac_coupling_capacitance_pF": 20.0,
        },
        afe={"input_resistance_ohm": 50.0, "voltage_gain": 10.0},
    )

    assert circuit.electrodes == ("left", "right")
    assert circuit.outputs == ("afe_out_0", "afe_out_1")
    assert circuit.times == pytest.approx(times)
    for element in ("I0", "Cbulk0", "Ccouple0", "Rbias0", "Cac0", "Rin0", "Eafe0"):
        assert element in circuit.netlist


def test_frontend_requires_one_increasing_time_axis() -> None:
    with pytest.raises(ValueError, match="must increase"):
        CurrentSource("readout", (0.0, 0.0), (1.0, 0.0))

    left = CurrentSource("left", (0.0, 1.0), (1.0, 0.0))
    right = CurrentSource("right", (0.0, 2.0), (0.0, 1.0))
    with pytest.raises(ValueError, match="share one time axis"):
        assemble_frontend(sources=(left, right), sensor_values={}, afe={})
