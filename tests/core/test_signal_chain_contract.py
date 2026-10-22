from __future__ import annotations

import pytest

from raser.core.current import induced_currents
from raser.core.current.vector import Vector
from raser.core.frontend import CurrentSource
from raser.core.frontend import assemble_frontend
from raser.core.interaction import from_energy_deposits
from raser.core.interaction import prescribed_track
from raser.core.metrics import measure_waveform


def test_interaction_creates_weighted_carrier_populations() -> None:
    generation = from_energy_deposits(
        [(1.0, 2.0, 3.0, 4.0)],
        [3.6e-6],
        material="Si",
    )
    track = prescribed_track(
        (0.0, 0.0, 0.0),
        (0.0, 0.0, 10.0),
        packets=2,
        pairs_per_um=5.0,
        time=2.0,
    )

    assert generation.ionized_pairs == pytest.approx((1.0,))
    assert generation.track_position == ((1.0, 2.0, 3.0, 4.0),)
    assert track.total_pairs == pytest.approx(50.0)
    assert track.track_position == (
        (0.0, 0.0, 2.5, 2.0),
        (0.0, 0.0, 7.5, 2.0),
    )


def test_current_frontend_and_metrics_share_one_waveform_contract() -> None:
    assert Vector(3.0, 4.0, 0.0).get_length() == 5.0
    current = induced_currents(
        charge_coulomb=2.0,
        times=(0.0, 1.0, 3.0),
        positions=((0.0, 0.0, 0.0), (0.5, 0.0, 0.0), (1.0, 0.0, 0.0)),
        weighting_potentials={
            "left": lambda point: point[0],
            "right": lambda point: 1.0 - point[0],
        },
    )

    assert current.times == pytest.approx((0.5, 2.0))
    assert current.values["left"] == pytest.approx((1.0, 0.5))
    assert current.values["right"] == pytest.approx((-1.0, -0.5))

    sources = tuple(
        CurrentSource(electrode, current.times, samples)
        for electrode, samples in current.values.items()
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
    assert circuit.times == pytest.approx(current.times)
    for element in ("I0", "Cbulk0", "Ccouple0", "Rbias0", "Cac0", "Rin0", "Eafe0"):
        assert element in circuit.netlist

    measurements = measure_waveform(
        times=(0.0, 1.0, 2.0, 3.0, 4.0),
        samples=(0.0, 1.0, 2.0, 1.0, 0.0),
        threshold=1.0,
        constant_fraction=0.5,
    )
    assert measurements.amplitude == 2.0
    assert measurements.time_of_arrival == 1.0
    assert measurements.time_over_threshold == 2.0
    assert measurements.constant_fraction_time == 1.0
    assert measurements.charge == pytest.approx(4.0)


def test_frontend_requires_one_increasing_time_axis() -> None:
    with pytest.raises(ValueError, match="must increase"):
        CurrentSource("readout", (0.0, 0.0), (1.0, 0.0))

    left = CurrentSource("left", (0.0, 1.0), (1.0, 0.0))
    right = CurrentSource("right", (0.0, 2.0), (0.0, 1.0))
    with pytest.raises(ValueError, match="share one time axis"):
        assemble_frontend(sources=(left, right), sensor_values={}, afe={})
