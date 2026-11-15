import json

import numpy as np
import pytest

from raser.core.device.build_device import Detector
from raser.core.device.build_device import device_file
from raser.core.frontend.device_circuit import device_sensor
from raser.core.frontend.device_circuit import junction_capacitance
from raser.core.frontend.spice import solve


def _device(**keys):
    """HPK-Si-PiN, 1.3 mm x 1.3 mm of 50 um silicon, without the capacitance
    of its file."""
    content = json.loads(device_file("HPK-Si-PiN").read_text(encoding="utf-8"))
    content.pop("capacitance_pF", None)
    return Detector("HPK-Si-PiN", {**content, **keys})


def test_junction_capacitance_is_the_measured_one_before_any_other():
    farad, source = junction_capacitance(_device(capacitance_pF=4.2), 3.9e-12)

    assert farad == pytest.approx(4.2e-12)
    assert source == "device file"


def test_junction_capacitance_of_the_field_where_none_is_measured():
    assert junction_capacitance(_device(), 3.9e-12) == (3.9e-12, "field")


def test_junction_capacitance_of_the_parallel_plate_where_there_is_no_other():
    # 11.5 x 8.854e-12 F/m x (1.3 mm)^2 / 50 um
    farad, source = junction_capacitance(_device())

    assert farad == pytest.approx(3.4416e-12, rel=1e-4)
    assert source == "parallel plate"


@pytest.mark.ngspice
def test_sensor_of_a_device_has_its_junction_capacitance_on_every_electrode():
    # 20 pF on a 50 Ohm load: each electrode answers its step with 1 ns
    wire = {
        "ports": {"in": "a", "out": "b"},
        "elements": {"R1": {"between": ["a", "b"], "ohm": 1e-6}},
    }
    load = {
        "ports": {"in": "a"},
        "elements": {"R1": {"between": ["a", "0"], "ohm": 50.0}},
    }
    dt_s = 20e-12
    times = -1e-9 + (np.arange(500) + 0.5) * dt_s
    step = np.where(times > 0, 1e-6, 0.0)

    sensor, values = device_sensor(_device(capacitance_pF=20.0), ["left", "right"])
    voltage = solve(
        {"stages": {"wire": wire}, "load": load},
        ["left", "right"],
        dt_s,
        [step, -2 * step],
        sensor,
    )

    assert values == {
        "junction_capacitance": {"farad": pytest.approx(20e-12), "from": "device file"},
        "between_electrodes": None,
        "undepleted_layer": None,
    }
    expected = 1e-6 * 50.0 * (1 - np.exp(-np.clip(times, 0, None) / 1e-9))
    off_the_jump = (times < 0) | (times > dt_s)
    assert voltage[0][off_the_jump] == pytest.approx(expected[off_the_jump], abs=2e-7)
    assert voltage[1][off_the_jump] == pytest.approx(
        -2 * expected[off_the_jump], abs=4e-7
    )
