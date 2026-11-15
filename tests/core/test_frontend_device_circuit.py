import json

import pytest

from raser.core.device.build_device import Detector
from raser.core.device.build_device import device_file
from raser.core.frontend.device_circuit import junction_capacitance


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
