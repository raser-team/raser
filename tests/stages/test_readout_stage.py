import json

import numpy as np
import pytest

from raser.core.current.currents import EventCurrents
from raser.core.current.currents import append_currents
from raser.core.device.build_device import device_file
from raser.core.readout.waveforms import read_waveforms
from raser.stages.readout import waveforms

pytestmark = pytest.mark.ngspice


def test_currents_on_the_cells_of_a_resistive_layer_come_out_on_its_strips(tmp_path):
    # 20 cells of 10 um under 1 kOhm a square, strips 1000 um long on the
    # cells 2 to 4 and 15 to 17 (from 0); 1 fC on the cell 7, cell8 by its
    # name, 25 um from the edge of the left strip and 75 um from that of the
    # right one, each on its 50 Ohm
    device = json.loads(device_file("SiC_LGAD_strip").read_text(encoding="utf-8"))
    device.update(
        {
            "read_ele_num": 20,
            "read_out_contact": [{"x_span": 0, "y_span": 0, "name": "cell"}],
            "p_x": 10,
            "l_y": 1000,
            "capacitance_pF": 0.0123,
            "resistive_layer": {
                "sheet_resistance_ohm": 1000.0,
                "strips": {"left": [2, 4], "right": [15, 17]},
            },
        }
    )
    dt = 20e-12
    current = np.zeros((20, 1000))
    current[7, :10] = 1e-15 / (10 * dt)
    append_currents(
        tmp_path / "current_0.h5",
        [f"cell{k}" for k in range(1, 21)],
        dt,
        EventCurrents(0, 0.0, current, current.sum(axis=1) * dt, 0.0),
    )
    kwargs = {
        "det_name": "SiC_LGAD_strip",
        "_files": {"device": device},
        "_slice_batch_paths": {"current": tmp_path, "readout": tmp_path},
        "amplifier": "Termination50",
    }

    waveforms(kwargs)

    record = read_waveforms(tmp_path / "readout_0.h5")
    assert record.electrodes == ["left", "right"]
    charge_fc = record.events[0].voltage.sum(axis=1) * dt / 50.0 * 1e15
    left_ohm, right_ohm = 25 + 50.0, 75 + 50.0
    assert charge_fc == pytest.approx(
        [right_ohm / (left_ohm + right_ohm), left_ohm / (left_ohm + right_ohm)],
        rel=0.01,
    )
