import json

import numpy as np
import pytest

from raser.core.device.build_device import Detector
from raser.core.device.build_device import device_file
from raser.core.field.assets import field_pickle_path
from raser.core.field.circuit_parameters import device_circuit
from raser.core.field.circuit_parameters import field_circuit
from raser.core.field.circuit_parameters import junction_capacitance
from raser.core.readout.spice import solve


def _device(**keys):
    """HPK-Si-PiN, 1.3 mm x 1.3 mm of 50 um silicon, without the capacitance
    of its file."""
    content = json.loads(device_file("HPK-Si-PiN").read_text(encoding="utf-8"))
    content.pop("capacitance_pF", None)
    return Detector("HPK-Si-PiN", {**content, **keys})


def test_junction_capacitance_is_the_measured_one_before_any_other():
    farad, source = junction_capacitance(_device(capacitance_pF=4.2), 3.9e-12)

    assert farad == pytest.approx(4.2e-12, abs=0)
    assert source == "device file"


def test_junction_capacitance_of_the_field_where_none_is_measured():
    assert junction_capacitance(_device(), 3.9e-12) == (3.9e-12, "field")


def test_junction_capacitance_of_the_parallel_plate_where_there_is_no_other():
    # 11.5 x 8.854e-12 F/m x (1.3 mm)^2 / 50 um
    farad, source = junction_capacitance(_device())

    assert farad == pytest.approx(3.4416e-12, rel=1e-4, abs=0)
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

    circuit, values = device_circuit(_device(capacitance_pF=20.0), ["left", "right"])
    voltage = solve(
        {"stages": {"wire": wire}, "load": load},
        ["left", "right"],
        dt_s,
        [step, -2 * step],
        circuit,
    )

    assert values == {
        "junction_capacitance": {
            "farad": pytest.approx(20e-12, abs=0),
            "from": "device file",
        },
        "between_electrodes": None,
        "bias_resistance": None,
        "coupling_capacitance": None,
        "undepleted_layer": None,
    }
    expected = 1e-6 * 50.0 * (1 - np.exp(-np.clip(times, 0, None) / 1e-9))
    off_the_jump = (times < 0) | (times > dt_s)
    assert voltage[0][off_the_jump] == pytest.approx(expected[off_the_jump], abs=2e-7)
    assert voltage[1][off_the_jump] == pytest.approx(
        -2 * expected[off_the_jump], abs=4e-7
    )


@pytest.mark.ngspice
def test_charge_through_the_coupling_capacitance_is_what_the_bias_resistance_leaves():
    # 1 uA for good on 20 pF: the electrode ends at 1 uA x 200 Ohm, and the
    # 30 pF to the read-out has taken 30 pF x 200 uV through the 50 Ohm load
    wire = {
        "ports": {"in": "a", "out": "b"},
        "elements": {"R1": {"between": ["a", "b"], "ohm": 1e-6}},
    }
    load = {
        "ports": {"in": "a"},
        "elements": {"R1": {"between": ["a", "0"], "ohm": 50.0}},
    }
    dt_s = 20e-12
    times = -1e-9 + (np.arange(5000) + 0.5) * dt_s
    step = np.where(times > 0, 1e-6, 0.0)

    circuit, values = device_circuit(
        _device(
            capacitance_pF=20.0, bias_resistance_ohm=200.0, coupling_capacitance_pF=30.0
        ),
        ["pad"],
    )
    voltage = solve(
        {"stages": {"wire": wire}, "load": load}, ["pad"], dt_s, [step], circuit
    )

    assert values["bias_resistance"] == {"ohm": 200.0}
    assert values["coupling_capacitance"] == {"farad": pytest.approx(30e-12, abs=0)}
    assert voltage[0].sum() * dt_s == pytest.approx(
        50.0 * 30e-12 * 1e-6 * 200.0, rel=2e-3, abs=0
    )
    assert abs(voltage[0][-1]) < 1e-7


@pytest.mark.ngspice
def test_charge_on_a_device_not_fully_depleted_is_held_back_by_its_undepleted_layer():
    # 1 nC at once across 20 pF, behind it 2 kOhm and 60 pF, read out on
    # 1 Ohm: 60 / 80 of it is out at once, and the 20 / 80 left on the
    # undepleted layer comes with 2 kOhm x 80 pF = 160 ns
    wire = {
        "ports": {"in": "a", "out": "b"},
        "elements": {"R1": {"between": ["a", "b"], "ohm": 1e-6}},
    }
    load = {
        "ports": {"in": "a"},
        "elements": {"R1": {"between": ["a", "0"], "ohm": 1.0}},
    }
    dt_s = 1e-9
    times = (np.arange(1000) + 0.5) * dt_s
    current = np.zeros(1000)
    current[0] = 1e-9 / dt_s
    chain = {"stages": {"wire": wire}, "load": load}

    from_file, values = device_circuit(
        _device(
            capacitance_pF=20.0,
            undepleted_resistance_ohm=2e3,
            undepleted_capacitance_pF=60.0,
        ),
        ["pad"],
        solved_undepleted=(9e3, 9e-12),
    )
    from_field, of_field = device_circuit(
        _device(capacitance_pF=20.0), ["pad"], solved_undepleted=(2e3, 60e-12)
    )
    voltage = solve(chain, ["pad"], dt_s, [current], from_file)[0]

    assert values["undepleted_layer"] == {
        "ohm": 2e3,
        "farad": pytest.approx(60e-12, abs=0),
        "from": "device file",
    }
    assert of_field["undepleted_layer"] == {
        "ohm": 2e3,
        "farad": 60e-12,
        "from": "field",
    }
    assert from_field.lines == from_file.lines
    late = times > 5e-9
    expected = 1.0 * 1e-9 * 20 / 80 / 160e-9 * np.exp(-(times - dt_s) / 160e-9)
    assert voltage[late] == pytest.approx(expected[late], rel=1e-2, abs=1e-8)
    assert voltage.sum() * dt_s == pytest.approx(1.0 * 1e-9, rel=1e-2)


def test_undepleted_layer_with_one_of_its_two_values_is_an_error():
    with pytest.raises(ValueError, match="alone"):
        device_circuit(_device(undepleted_resistance_ohm=2e3), ["pad"])


def test_row_of_strips_with_an_undepleted_layer_is_an_error():
    with pytest.raises(ValueError, match="undepleted"):
        device_circuit(_strips(), ["top1"], row=ROW, solved_undepleted=(2e3, 60e-12))


def _strips(**keys):
    """ITk-Si-strip with strips 5 mm long."""
    content = json.loads(device_file("ITk-Si-strip").read_text(encoding="utf-8"))
    return Detector("ITk-Si-strip", {**content, "l_y": 5000, **keys})


# of a strip, per cm: 1 pF in all, 0.5 pF to the two nearest strips together,
# 0.125 pF to the two next ones, 0.05 pF to the third ones, which is not coupled
ROW = {
    "unit": "F/cm",
    "of": "top",
    "total": 1.0e-12,
    "to": {
        "neighbour1": 0.5e-12,
        "neighbour2": 0.125e-12,
        "neighbour3": 0.05e-12,
        "bot": 0.325e-12,
    },
    "neighbours_coupled": 2,
}


@pytest.mark.ngspice
def test_charge_on_one_strip_of_a_row_is_shared_by_the_capacitances_between_them():
    # nothing leads the charge away within the run: the strips come to the
    # voltages their capacitances give. Each strip is 0.5 cm long and has
    # 0.5 pF in all; two strips have 0.125 pF between them one place apart
    # and 0.03125 pF two places apart
    wire = {
        "ports": {"in": "a", "out": "b"},
        "elements": {"R1": {"between": ["a", "b"], "ohm": 1e-6}},
    }
    open_end = {
        "ports": {"in": "a"},
        "elements": {"R1": {"between": ["a", "0"], "ohm": 1e12}},
    }
    electrodes = ["top1", "top2", "top3", "top4"]
    dt_s = 20e-12
    currents = np.zeros((4, 200))
    currents[1, 10:60] = 1e-6  # 1 fC on the second strip

    circuit, values = device_circuit(_strips(), electrodes, row=ROW)
    voltage = solve(
        {"stages": {"wire": wire}, "load": open_end},
        electrodes,
        dt_s,
        currents,
        circuit,
    )

    assert values["junction_capacitance"] == {
        "farad": pytest.approx(0.5e-12, abs=0),
        "from": "field",
    }
    assert values["between_electrodes"] == {
        "farad": [
            pytest.approx(0.125e-12, abs=0),
            pytest.approx(0.03125e-12, abs=0),
        ],
        "from": "field",
    }
    near, far = 0.125e-12, 0.03125e-12
    capacitances = np.array(
        [
            [0.5e-12, -near, -far, 0.0],
            [-near, 0.5e-12, -near, -far],
            [-far, -near, 0.5e-12, -near],
            [0.0, -far, -near, 0.5e-12],
        ]
    )
    expected = np.linalg.solve(capacitances, [0.0, 1e-15, 0.0, 0.0])
    assert voltage[:, -1] == pytest.approx(expected, rel=1e-3)


def test_capacitances_of_a_row_are_not_taken_for_a_device_without_strips():
    with pytest.raises(ValueError, match="not a row of strips"):
        device_circuit(_device(), ["top"], row=ROW)


def test_strip_with_less_capacitance_in_all_than_to_the_other_strips_is_an_error():
    # 0.1 pF measured in all; the field gives 0.125 pF to the nearest strip
    with pytest.raises(ValueError, match="to the other strips"):
        device_circuit(_strips(capacitance_pF=0.1), ["top1", "top2"], row=ROW)


def test_strips_of_a_row_have_the_bias_resistance_and_coupling_of_the_device():
    circuit, _ = device_circuit(
        _strips(bias_resistance_ohm=1.5e6, coupling_capacitance_pF=10.0),
        ["top1", "top2"],
        row=ROW,
    )

    assert "Rtop2_bias top2_pad 0 1500000" in circuit.lines
    assert "Ctop2_coupling top2_pad top2_port 1e-11" in circuit.lines
    assert "Ctop1_top2 top1_pad top2_pad" in " ".join(circuit.lines)
    assert circuit.outputs == {"top1": "top1_port", "top2": "top2_port"}


def test_field_gives_a_planar_device_its_undepleted_bulk_for_its_area(tmp_path):
    # 10 um of the 50 um left undepleted at 100 V: 9.4 Ohm cm^2 and 262 pF per
    # cm^2 of the field, on the 0.0169 cm^2 of HPK-Si-PiN
    device = _device(bias={"electrode": "top", "voltage": 100.0})
    (tmp_path / "run.json").write_text(
        json.dumps(
            {
                "files": {"device": {"det_name": "HPK-Si-PiN", "area_factor": 0.0169}},
                "solved": {"undepleted": [100.0]},
            }
        )
    )
    (tmp_path / "100.0V.undepleted.json").write_text(
        json.dumps(
            {
                "undepleted_width_um": 10.0,
                "specific_resistance_ohm_cm2": 9.4,
                "specific_capacitance_pF": 262.0,
            }
        )
    )

    row, undepleted = field_circuit(tmp_path, device)

    assert row is None
    assert undepleted == (
        pytest.approx(9.4 / 0.0169, rel=1e-12),
        pytest.approx(262.0e-12 * 0.0169, rel=1e-12, abs=0),
    )


def test_field_gives_a_row_of_strips_the_capacitances_it_stored(tmp_path):
    device = _strips()
    stored = field_pickle_path(
        tmp_path / "weightingfield" / "top", "Capacitance", device.voltage
    ).with_suffix(".json")

    with pytest.raises(FileNotFoundError, match="-wf"):
        field_circuit(tmp_path, device)

    stored.parent.mkdir(parents=True)
    stored.write_text(json.dumps(ROW))
    row, undepleted = field_circuit(tmp_path, device)

    # a strip device of two dimensions has no slab of undepleted bulk
    assert row == ROW
    assert undepleted is None
