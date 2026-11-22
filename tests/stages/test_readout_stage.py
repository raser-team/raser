import json

import numpy as np
import pytest

from raser.core.current.currents import EventCurrents
from raser.core.current.currents import append_currents
from raser.core.device.build_device import device_file
from raser.core.field.assets import field_pickle_path
from raser.core.readout.waveforms import read_circuit_values
from raser.core.readout.waveforms import read_waveforms
from raser.stages import readout
from raser.stages.readout import waveforms

pytestmark = pytest.mark.ngspice


DT_S = 20e-12


def _resistive_strips(tmp_path):
    """Arguments of the slice for 20 RC nodes of 10 um under 1 kOhm a square,
    strips 1000 um long on the RC nodes 2 to 4 and 15 to 17 (from 0), and a
    currents file with 1 fC on the RC node 7, node8 by its name, 25 um from the
    edge of the left strip and 75 um from that of the right one."""
    device = json.loads(device_file("SiC_LGAD_strip").read_text(encoding="utf-8"))
    device.update(
        {
            "read_ele_num": 20,
            "read_out_contact": [{"x_span": 0, "y_span": 0, "name": "node"}],
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
        tmp_path / "current.h5",
        [f"node{k}" for k in range(1, 21)],
        DT_S,
        EventCurrents(0, 0.0, current, current.sum(axis=1) * DT_S, 0.0),
    )
    return {
        "det_name": "SiC_LGAD_strip",
        "_files": {"device": device},
        "_node_paths": {"current": tmp_path, "readout": tmp_path},
        "amplifier": "Termination50",
    }


def test_currents_on_the_rc_nodes_of_a_resistive_layer_come_out_on_its_strips(tmp_path):
    # each strip on its 50 Ohm
    waveforms(_resistive_strips(tmp_path))

    record = read_waveforms(tmp_path / "readout.h5")
    assert record.electrodes == ["left", "right"]
    # the RC nodes lie below the electrode on 740 V: they collect holes
    assert record.pulse_edge == ["rising", "rising"]
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

    record = read_waveforms(tmp_path / "readout.h5")
    charge_fc = record.events[0].voltage.sum(axis=1) * DT_S / 50.0 * 1e15
    left_ohm, right_ohm = 100 + 50.0, 300 + 50.0
    assert charge_fc == pytest.approx(
        [right_ohm / (left_ohm + right_ohm), left_ohm / (left_ohm + right_ohm)],
        rel=0.01,
    )
    assert read_circuit_values(tmp_path / "readout.h5")["sheet_resistance"] == {
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


def test_a_planar_device_not_fully_depleted_is_read_out_through_its_undepleted_bulk(
    tmp_path, monkeypatch
):
    # HPK-Si-PiN at 100 V with 10 um undepleted, as its field gives it: the
    # circuit of the device gets the R and C of that bulk for its area, 556
    # Ohm and 4.4 pF. All of 1 fC still leaves through the 50 Ohm, but held
    # back: on average after 2.2 ns, where the depleted device alone, 3.44
    # pF on 50 Ohm, lets it out after 0.26 ns
    field = tmp_path / "field"
    field.mkdir()
    (field / "run.json").write_text(
        json.dumps(
            {
                "files": {"device": {"det_name": "HPK-Si-PiN", "area_factor": 0.0169}},
                "solved": {"undepleted": [100.0]},
            }
        )
    )
    (field / "100.0V.undepleted.json").write_text(
        json.dumps(
            {
                "undepleted_width_um": 10.0,
                "specific_resistance_ohm_cm2": 9.4,
                "specific_capacitance_pF": 262.0,
            }
        )
    )
    monkeypatch.setattr(readout, "solved_field", lambda *_: field)
    device = json.loads(device_file("HPK-Si-PiN").read_text(encoding="utf-8"))
    device["bias"] = {"electrode": "top", "voltage": 100.0}
    current = np.zeros((1, 2000))
    current[0, :10] = 1e-15 / (10 * DT_S)
    append_currents(
        tmp_path / "current.h5",
        ["top"],
        DT_S,
        EventCurrents(0, 0.0, current, current.sum(axis=1) * DT_S, 0.0),
    )

    waveforms(
        {
            "det_name": "HPK-Si-PiN",
            "_files": {"device": device},
            "_node_paths": {"current": tmp_path, "readout": tmp_path},
            "amplifier": "Termination50",
        }
    )

    assert read_circuit_values(tmp_path / "readout.h5")["undepleted_layer"] == {
        "ohm": pytest.approx(9.4 / 0.0169, rel=1e-12),
        "farad": pytest.approx(262.0e-12 * 0.0169, rel=1e-12, abs=0),
        "from": "field",
    }
    voltage = read_waveforms(tmp_path / "readout.h5").events[0].voltage[0]
    times = (np.arange(voltage.size) + 0.5) * DT_S
    assert voltage.sum() * DT_S / 50.0 * 1e15 == pytest.approx(1.0, rel=0.01)
    assert np.sum(times * voltage) / np.sum(voltage) > 1.5e-9


def test_a_row_of_strips_is_read_out_through_the_capacitances_its_field_stored(
    tmp_path, monkeypatch
):
    # four strips 5 mm long of ITk-Si-strip, 1 pF per cm in all, 0.5 pF per cm
    # to the two nearest together: 0.125 pF between neighbours
    field = tmp_path / "field"
    device = json.loads(device_file("ITk-Si-strip").read_text(encoding="utf-8"))
    device.update({"read_ele_num": 4, "l_y": 5000})
    stored = field_pickle_path(
        field / "weightingfield" / "top", "Capacitance", device["bias"]["voltage"]
    ).with_suffix(".json")
    stored.parent.mkdir(parents=True)
    stored.write_text(
        json.dumps(
            {
                "unit": "F/cm",
                "of": "top",
                "total": 1.0e-12,
                "to": {"neighbour1": 0.5e-12, "bot": 0.5e-12},
                "neighbours_coupled": 1,
            }
        )
    )
    # fully depleted at its bias
    bias_v = float(device["bias"]["voltage"])
    (field / "run.json").write_text(
        json.dumps(
            {
                "files": {"device": {"det_name": "ITk-Si-strip"}},
                "solved": {"undepleted": [bias_v]},
            }
        )
    )
    (field / f"{bias_v}V.undepleted.json").write_text(
        json.dumps({"undepleted_width_um": 0.0})
    )
    monkeypatch.setattr(readout, "solved_field", lambda *_: field)
    # 1 fC on the second strip
    current = np.zeros((4, 200))
    current[1, :10] = 1e-15 / (10 * DT_S)
    append_currents(
        tmp_path / "current.h5",
        [f"top{k}" for k in range(1, 5)],
        DT_S,
        EventCurrents(0, 0.0, current, current.sum(axis=1) * DT_S, 0.0),
    )

    waveforms(
        {
            "det_name": "ITk-Si-strip",
            "_files": {"device": device},
            "_node_paths": {"current": tmp_path, "readout": tmp_path},
            "amplifier": "Termination50",
        }
    )

    values = read_circuit_values(tmp_path / "readout.h5")
    assert values["between_electrodes"] == {
        "farad": [pytest.approx(0.125e-12, rel=1e-12, abs=0)],
        "from": "field",
    }
    assert values["junction_capacitance"] == {
        "farad": pytest.approx(0.5e-12, rel=1e-12, abs=0),
        "from": "field",
    }
    # the neighbours see it through the capacitances between the strips
    voltage = read_waveforms(tmp_path / "readout.h5").events[0].voltage
    peaks = np.abs(voltage).max(axis=1)
    assert peaks[0] > 0.05 * peaks[1] and peaks[2] > 0.05 * peaks[1]


def test_a_device_without_a_measured_capacitance_takes_the_one_its_field_solved(
    tmp_path, monkeypatch
):
    # HPK-Si-PiN without its measured 3.44 pF, its field solved at 200 V with
    # 1000 pF per cm^2 on 0.0169 cm^2: 16.9 pF. 1 fC in 50 ps on 50 Ohm, far
    # quicker than the 0.85 ns of 50 Ohm on 16.9 pF: the peak is Q / C
    field = tmp_path / "field"
    field.mkdir()
    (field / "run.json").write_text(
        json.dumps(
            {
                "files": {"device": {"det_name": "HPK-Si-PiN", "area_factor": 0.0169}},
                "solved": {"undepleted": [200.0], "capacitance": [200.0]},
            }
        )
    )
    (field / "200.0V.undepleted.json").write_text(
        json.dumps({"undepleted_width_um": 0.0})
    )
    (field / "200.0V.cv.json").write_text(
        json.dumps({"specific_capacitance_pF": 1000.0, "area_factor": 0.0169})
    )
    monkeypatch.setattr(readout, "solved_field", lambda *_: field)
    device = json.loads(device_file("HPK-Si-PiN").read_text(encoding="utf-8"))
    device.pop("capacitance_pF")
    dt = 5e-12
    current = np.zeros((1, 400))
    current[0, :10] = -1e-15 / (10 * dt)
    append_currents(
        tmp_path / "current.h5",
        ["top"],
        dt,
        EventCurrents(0, 0.0, current, current.sum(axis=1) * dt, 0.0),
    )

    waveforms(
        {
            "det_name": "HPK-Si-PiN",
            "_files": {"device": device},
            "_node_paths": {"current": tmp_path, "readout": tmp_path},
            "amplifier": "Termination50",
        }
    )

    voltage = read_waveforms(tmp_path / "readout.h5").events[0].voltage[0]
    assert -voltage.min() == pytest.approx(1e-15 / 16.9e-12, rel=0.1)
