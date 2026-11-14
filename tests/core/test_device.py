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


def test_the_electrodes_key_lays_out_the_readout_and_the_name_does_not() -> None:
    def device(**keys: object) -> Detector:
        content = {**_content(), "read_ele_num": 3, "p_x": 10.0}
        content.update(x_ele_num=2, y_ele_num=2, p_y=20.0, **keys)
        return Detector("HPK-Si-PiN", content)

    strip = device(electrodes="strip")
    pixel = device(electrodes="pixel")
    pad = device(det_model="strip")

    assert (strip.read_ele_num, strip.x_ele_num, strip.y_ele_num) == (3, 3, 1)
    assert (strip.p_x, strip.p_y) == (10.0, strip.l_y)
    assert strip._readout_area_um2() == 10.0 * strip.l_y
    assert (pixel.read_ele_num, pixel.p_x, pixel.p_y) == (4, 10.0, 20.0)
    assert pixel._readout_area_um2() == 200.0
    assert (pad.read_ele_num, pad.x_ele_num, pad.y_ele_num) == (1, 1, 1)
    assert (pad.p_x, pad.p_y) == (pad.l_x, pad.l_y)
    assert pad._readout_area_um2() == pad.l_x * pad.l_y
