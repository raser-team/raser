import json

import numpy as np
import pytest

from raser.core.current.currents import EventCurrents
from raser.core.current.currents import append_currents
from raser.core.device.build_device import device_file
from raser.core.readout.waveforms import read_circuit_values
from raser.core.readout.waveforms import read_waveforms
from raser.stages.readout import waveforms

pytestmark = pytest.mark.ngspice


DT_S = 20e-12


def _resistive_strips(tmp_path):
    """Arguments of the slice for 20 cells of 10 um under 1 kOhm a square,
    strips 1000 um long on the cells 2 to 4 and 15 to 17 (from 0), and a
    currents file with 1 fC on the cell 7, cell8 by its name, 25 um from the
    edge of the left strip and 75 um from that of the right one."""
    device = json.loads(device_file("SiC_LGAD_strip").read_text(encoding="utf-8"))
    device.update(
        {
            "read_ele_num": 20,
            "read_out_contact": [{"x_span": 0, "y_span": 0, "name": "cell"}],
            "p_x": 10,
            "l_y": 1000,
            "capacitance_pF": 0.0123,
            "resistive_layer": {
                "sheet_resistance": 1000.0,
                "strips": {"left": [2, 4], "right": [15, 17]},
            },
        }
    )
    current = np.zeros((20, 1000))
    current[7, :10] = 1e-15 / (10 * DT_S)
    append_currents(
        tmp_path / "current_0.h5",
        [f"cell{k}" for k in range(1, 21)],
        DT_S,
        EventCurrents(0, 0.0, current, current.sum(axis=1) * DT_S, 0.0),
    )
    return {
        "det_name": "SiC_LGAD_strip",
        "_files": {"device": device},
        "_slice_batch_paths": {"current": tmp_path, "readout": tmp_path},
        "amplifier": "Termination50",
    }


def test_currents_on_the_cells_of_a_resistive_layer_come_out_on_its_strips(tmp_path):
    # each strip on its 50 Ohm
    waveforms(_resistive_strips(tmp_path))

    record = read_waveforms(tmp_path / "readout_0.h5")
    assert record.electrodes == ["left", "right"]
    charge_fc = record.events[0].voltage.sum(axis=1) * DT_S / 50.0 * 1e15
    left_ohm, right_ohm = 25 + 50.0, 75 + 50.0
    assert charge_fc == pytest.approx(
        [right_ohm / (left_ohm + right_ohm), left_ohm / (left_ohm + right_ohm)],
        rel=0.01,
    )


def test_sheet_resistance_given_to_the_slice_takes_the_place_of_the_device_file(
    tmp_path,
):
    # the same hit, the layer at 4 kOhm a square instead of the 1 kOhm of the
    # file: 100 and 300 Ohm of layer to the two strips
    kwargs = _resistive_strips(tmp_path)
    kwargs["sheet_resistance"] = 4000.0

    waveforms(kwargs)

    record = read_waveforms(tmp_path / "readout_0.h5")
    charge_fc = record.events[0].voltage.sum(axis=1) * DT_S / 50.0 * 1e15
    left_ohm, right_ohm = 100 + 50.0, 300 + 50.0
    assert charge_fc == pytest.approx(
        [right_ohm / (left_ohm + right_ohm), left_ohm / (left_ohm + right_ohm)],
        rel=0.01,
    )
    assert read_circuit_values(tmp_path / "readout_0.h5")["sheet_resistance"] == {
        "ohm": 4000.0,
        "from": "chosen",
    }


def test_sheet_resistance_for_a_device_without_a_resistive_layer_is_refused(
    tmp_path,
):
    kwargs = _resistive_strips(tmp_path)
    kwargs["_files"]["device"].pop("resistive_layer")
    kwargs["sheet_resistance"] = 4000.0

    with pytest.raises(ValueError, match="no resistive layer"):
        waveforms(kwargs)
