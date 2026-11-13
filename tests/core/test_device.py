from __future__ import annotations

import json

from raser.core.device.build_device import Detector
from raser.core.device.build_device import device_file


def _content() -> dict:
    return json.loads(device_file("HPK-Si-PiN").read_text(encoding="utf-8"))


def test_a_device_and_the_content_it_was_built_from_do_not_change_each_other() -> None:
    content = _content()
    device = Detector("HPK-Si-PiN", content)

    content["bias"]["voltage"] = 1.0
    content["doping"]["Donors"] = "0"
    assert device.device_dict["bias"]["voltage"] == _content()["bias"]["voltage"]
    assert device.doping["Donors"] == _content()["doping"]["Donors"]

    device.device_dict["mesh"]["1D_mesh"]["region"][0]["material"] = "gas"
    assert content["mesh"]["1D_mesh"]["region"][0]["material"] == "Silicon"
