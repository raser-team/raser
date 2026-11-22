import json

import numpy as np
import pytest

from raser.core.device.build_device import Detector
from raser.core.device.build_device import device_file
from raser.core.field import implanted_aluminium
from raser.core.field.circuit_parameters import device_grid
from raser.core.field.circuit_parameters import device_row
from raser.core.field.circuit_parameters import sheet_resistance
from raser.core.field.resistive_layer import resistive_grid
from raser.core.field.resistive_layer import resistive_row
from raser.core.readout.spice import solve

pytestmark = pytest.mark.ngspice

# every read-out on 50 Ohm, through a wire
WIRE = {
    "ports": {"in": "a", "out": "b"},
    "elements": {"R1": {"between": ["a", "b"], "ohm": 1e-6}},
}
LOAD = {
    "ports": {"in": "a"},
    "elements": {"R1": {"between": ["a", "0"], "ohm": 50.0}},
}
ON_THE_LOAD = {"stages": {"wire": WIRE}, "load": LOAD}
DT_S = 20e-12
BINS = 1000
# 1 fC in the first ten bins
PULSE = np.where(np.arange(BINS) < 10, 1e-15 / (10 * DT_S), 0.0)
# a layer of 1 kOhm a square with 1 uF / m^2 under it: RC nodes of 10 x 1000 um
# have 10 fF each and 10 Ohm from one middle to the next
RC_NODE_M, LENGTH_M = 10e-6, 1e-3
SHEET_OHM, PER_AREA_F_M2 = 1000.0, 1e-6


def _layer_ohm(um):
    """Resistance of the layer across um of it, along the length of the row."""
    return SHEET_OHM * um * 1e-6 / LENGTH_M


def _charges(circuit, rc_node):
    """Charge [fC] that 1 fC on an RC node sends through the load of each read-out."""
    rc_nodes = list(circuit.sources)
    currents = np.zeros((len(rc_nodes), BINS))
    currents[rc_nodes.index(rc_node)] = PULSE
    voltage = solve(ON_THE_LOAD, rc_nodes, DT_S, currents, circuit)
    return voltage.sum(axis=1) * DT_S / 50.0 * 1e15


def test_charge_between_two_strips_is_shared_by_the_distances_to_them():
    # strips on the RC nodes 2 to 4 and 15 to 17; RC nodes beyond them end open
    rc_nodes = [f"n{k}" for k in range(20)]
    circuit = resistive_row(
        rc_nodes,
        RC_NODE_M,
        LENGTH_M,
        SHEET_OHM,
        PER_AREA_F_M2,
        {"left": (2, 4), "right": (15, 17)},
    )
    # the layer between the strips runs from the edge of the RC node 4 to that
    # of the RC node 15, from 50 to 150 um. All the charge leaves through the
    # loads, shared as a steady current would be
    for rc_node in (5, 8, 12, 14):
        to_left, to_right = _charges(circuit, f"n{rc_node}")
        centre_um = (rc_node + 0.5) * 10
        left_ohm = _layer_ohm(centre_um - 50) + 50.0
        right_ohm = _layer_ohm(150 - centre_um) + 50.0
        share = right_ohm / (left_ohm + right_ohm)
        assert to_left == pytest.approx(share, rel=0.01)
        assert to_right == pytest.approx(1 - share, rel=0.01)
    assert sum(_charges(circuit, "n0")) == pytest.approx(1, rel=0.01)
    # an RC node beyond a strip feeds the strip, which passes some of it on
    to_left, to_right = _charges(circuit, "n18")
    beyond = 50.0 / (50.0 + _layer_ohm(100) + 50.0)
    assert to_left == pytest.approx(beyond, rel=0.01)


def test_charge_beside_a_grounded_contact_is_partly_lost_to_it():
    rc_nodes = [f"n{k}" for k in range(12)]
    circuit = resistive_row(
        rc_nodes,
        RC_NODE_M,
        LENGTH_M,
        SHEET_OHM,
        PER_AREA_F_M2,
        {"strip": (0, 1)},
        {"ring": (10, 11)},
    )
    # from the middle of the RC node 5: 35 um of layer to the strip, on its
    # load, and 45 um to the ring
    (to_strip,) = _charges(circuit, "n5")
    to_strip_ohm = _layer_ohm(35) + 50.0
    assert to_strip == pytest.approx(
        _layer_ohm(45) / (_layer_ohm(45) + to_strip_ohm), rel=0.01
    )


@pytest.mark.parametrize("along", ["x", "y"])
def test_grid_one_rc_node_wide_is_a_row(along):
    count = 12
    rc_nodes = [f"n{k}" for k in range(count)]
    strips = {"left": (1, 2), "right": (8, 9)}
    row = resistive_row(rc_nodes, RC_NODE_M, LENGTH_M, SHEET_OHM, PER_AREA_F_M2, strips)
    if along == "x":
        counts, widths = (count, 1), (RC_NODE_M, LENGTH_M)
        pads = {name: (first, last, 0, 0) for name, (first, last) in strips.items()}
    else:
        counts, widths = (1, count), (LENGTH_M, RC_NODE_M)
        pads = {name: (0, 0, first, last) for name, (first, last) in strips.items()}
    grid = resistive_grid(rc_nodes, counts, widths, SHEET_OHM, PER_AREA_F_M2, pads)

    currents = np.zeros((count, BINS))
    currents[4] = PULSE
    np.testing.assert_allclose(
        solve(ON_THE_LOAD, rc_nodes, DT_S, currents, grid),
        solve(ON_THE_LOAD, rc_nodes, DT_S, currents, row),
        rtol=1e-6,
        atol=1e-12,
    )


def test_pads_coupled_to_a_grounded_layer_carry_no_net_charge():
    # 5 x 5 RC nodes of 100 um under 1 kOhm a square, 70 um of SiC below, a pad
    # over the RC node (1, 1) and one over (3, 3) on 0.5 um of oxide, the layer
    # held on ground at a corner. The charge leaves through the ground, in
    # some ns; the pads see it pass
    rc_nodes = [f"n{k}" for k in range(25)]
    circuit = resistive_grid(
        rc_nodes,
        (5, 5),
        (100e-6, 100e-6),
        1e3,
        9.7 * 8.854e-12 / 70e-6,
        {"near": (1, 1, 1, 1), "far": (3, 3, 3, 3)},
        coupling_per_area_f_m2=3.9 * 8.854e-12 / 0.5e-6,
        grounded={"corner": [(0, 0, 0, 0)]},
    )
    dt = 100e-12
    currents = np.zeros((25, BINS))
    currents[1 * 5 + 2, 0] = 1e-15 / dt  # beside the near pad
    voltage = solve(ON_THE_LOAD, rc_nodes, dt, currents, circuit)

    near, far = voltage
    assert np.abs(near).max() > 2 * np.abs(far).max()
    for pad in (near, far):
        assert abs(pad.sum()) < 0.02 * np.abs(pad).sum()


def _rsd_strips(**layer):
    """A device of RC nodes 10 um wide and 1000 um long, with 12.3 fF each, and
    the two strips of the tests above on its resistive layer."""
    content = json.loads(device_file("SiC_LGAD_strip").read_text(encoding="utf-8"))
    return Detector(
        "SiC_LGAD_strip",
        {
            **content,
            "p_x": 10,
            "l_y": 1000,
            "capacitance_pF": 0.0123,
            "resistive_layer": {
                "strips": {"left": [2, 4], "right": [15, 17]},
                **layer,
            },
        },
    )


def test_strips_of_a_device_share_the_charge_through_the_layer_it_gives():
    rc_nodes = [f"n{k}" for k in range(20)]
    circuit, values = device_row(_rsd_strips(sheet_resistance=1000.0), rc_nodes)

    assert values == {
        "rc_node_capacitance": {
            "farad": pytest.approx(12.3e-15, abs=0),
            "from": "device file",
        },
        "sheet_resistance": {"ohm": 1000.0, "from": "device file"},
        "coupling_per_area_f_m2": None,
        "undepleted_layer": None,
    }
    # each RC node with the capacitance of the device under it
    assert "Clayer_n8 layer_n8 0 1.23e-14" in circuit.lines
    to_left, to_right = _charges(circuit, "n8")
    left_ohm = _layer_ohm(85 - 50) + 50.0
    right_ohm = _layer_ohm(150 - 85) + 50.0
    assert to_left == pytest.approx(right_ohm / (left_ohm + right_ohm), rel=0.01)


def test_sheet_resistance_of_the_implanted_layer_where_the_device_gives_none():
    implanted = {"implanted": 3e15, "thickness": 0.3, "anneal": 1775.0}

    ohm, source = sheet_resistance(_rsd_strips(**implanted))
    given, _ = sheet_resistance(_rsd_strips(sheet_resistance=500.0, **implanted))

    assert source == "implanted layer"
    assert ohm == implanted_aluminium.sheet_resistance(3e15, 0.3e-4, 1775.0, 300.0)
    assert given == 500.0


def test_pads_of_a_device_are_coupled_through_the_dielectric_it_gives():
    content = json.loads(device_file("SiC_LGAD_strip").read_text(encoding="utf-8"))
    content.pop("read_ele_num")
    device = Detector(
        "SiC_LGAD_strip",
        {
            **content,
            "electrodes": "pixel",
            "p_x": 100,
            "p_y": 100,
            "x_ele_num": 2,
            "y_ele_num": 2,
            "capacitance_pF": 0.1,
            "resistive_layer": {
                "sheet_resistance": 1000.0,
                "pads": {"pad": [0, 0, 0, 0]},
                "grounded": {"ring": [[1, 1, 1, 1]]},
                "coupling": {"thickness": 0.5, "permittivity": 3.9},
            },
        },
    )

    circuit, values = device_grid(device, ["a", "b", "c", "d"])

    # 3.9 x 8.854e-12 F/m over 0.5 um, on an RC node of 100 um x 100 um
    assert values["coupling_per_area_f_m2"] == pytest.approx(6.906e-5, rel=1e-3)
    assert "Cpad_a layer_a pad_pad 6.906" in "\n".join(circuit.lines)


@pytest.mark.parametrize("span", [(2, 2, 0, 0), (1, 2, 0, 0), (0, 0, -1, 0)])
def test_pad_off_the_layer_is_refused_whether_in_contact_or_coupled(span):
    for coupling in (None, 1e-4):
        with pytest.raises(ValueError, match="layer has 2 by 1 RC nodes"):
            resistive_grid(
                ["a", "b"], (2, 1), (1e-4, 1e-4), 1e3, 1e-5, {"pad": span}, coupling
            )


def test_strips_on_a_dielectric_over_a_grounded_layer_carry_no_net_charge():
    # the row of the tests above, the layer held on ground at the RC node 19,
    # the strips over 0.5 um of oxide: the charge leaves through the ground,
    # the strips see it pass. In contact they take what the ring does not
    coupled = _rsd_strips(
        sheet_resistance=1000.0,
        grounded={"ring": [19, 19]},
        coupling={"thickness": 0.5, "permittivity": 3.9},
    )
    rc_nodes = [f"n{k}" for k in range(20)]

    circuit, values = device_row(coupled, rc_nodes)
    to_left, to_right = _charges(circuit, "n8")

    assert values["coupling_per_area_f_m2"] == pytest.approx(6.906e-5, rel=1e-3)
    assert abs(to_left) < 0.01 and abs(to_right) < 0.01
    in_contact, _ = device_row(
        _rsd_strips(sheet_resistance=1000.0, grounded={"ring": [19, 19]}), rc_nodes
    )
    assert sum(_charges(in_contact, "n8")) > 0.5
