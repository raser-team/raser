import json

import numpy as np
import pytest

from raser.core.current.cal_current import electrode_names
from raser.core.device.build_device import Detector
from raser.core.device.build_device import device_file
from raser.core.field.circuit_parameters import device_row
from raser.core.readout.network import impulse_response
from raser.core.field.resistive_layer import shares

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
DT_S = 10e-12
# a layer of 1 kOhm a square, 1000 um long: 1 Ohm per um across it
SHEET_OHM, LENGTH_UM = 1000.0, 1000.0


def _device(**layer):
    """A device of 20 RC nodes 10 um wide and 1000 um long on 200 um, 12.3 fF
    each, with strips on the RC nodes 2 to 4 (20 to 50 um) and 15 to 17 (150 to
    180 um) of its resistive layer. Over keys of the device file give the
    halved RC nodes, as 40 RC nodes of 5 um with 6.15 fF each."""
    return _build({}, layer)


def _half_rc_nodes(**layer):
    return _build(
        {
            "read_ele_num": 40,
            "p_x": 5,
            "capacitance_pF": 0.00615,
        },
        layer,
        strips={"left": [4, 9], "right": [30, 35]},
    )


def _build(over, layer, strips=None):
    content = json.loads(device_file("SiC_LGAD_strip").read_text(encoding="utf-8"))
    return Detector(
        "SiC_LGAD_strip",
        {
            **content,
            "read_ele_num": 20,
            "read_out_contact": [{"x_span": 0, "y_span": 0, "name": "node"}],
            "p_x": 10,
            "l_x": 200,
            "l_y": 1000,
            "capacitance_pF": 0.0123,
            **over,
            "resistive_layer": {
                "strips": strips or {"left": [2, 4], "right": [15, 17]},
                **layer,
            },
        },
    )


def _response(my_d, points_um):
    """Voltage [V] of the strips, shape (points, strips, bins), for 1 fC on
    each point."""
    rc_nodes = electrode_names(my_d.read_out_contact, my_d.read_ele_num)
    circuit, _ = device_row(my_d, rc_nodes)
    return impulse_response(my_d, circuit, ON_THE_LOAD, points_um, dt=DT_S)


def _charges(voltage):
    """Charge [fC] through the 50 Ohm load of each read-out."""
    return voltage.sum(axis=-1) * DT_S / 50.0 * 1e15


def _layer_ohm(um):
    """Resistance of the layer across um of it."""
    return SHEET_OHM * um / LENGTH_UM


def _share_to_left(x_um):
    """Part of a steady current that leaves through the left strip: the layer
    runs from the inner edge of the left strip, 50 um, to that of the right
    one, 150 um, and each strip ends on its 50 Ohm load."""
    left_ohm = _layer_ohm(x_um - 50) + 50.0
    right_ohm = _layer_ohm(150 - x_um) + 50.0
    return right_ohm / (left_ohm + right_ohm)


def test_charge_between_two_strips_is_shared_by_the_distances_to_them():
    my_d = _device(sheet_resistance=1000.0)
    points = [60.0, 75.0, 80.0, 120.0, 140.0]

    charges = _charges(_response(my_d, points))

    for x_um, (to_left, to_right) in zip(points, charges):
        assert to_left == pytest.approx(_share_to_left(x_um), rel=0.01)
        assert to_right == pytest.approx(1 - _share_to_left(x_um), rel=0.01)


def test_charge_shared_is_the_same_for_rc_nodes_of_half_the_width():
    # the same coordinates, the same strips at 20 to 50 um and 150 to 180 um,
    # on RC nodes of 10 um and of 5 um
    points = [75.0, 120.0]

    coarse = _charges(_response(_device(sheet_resistance=1000.0), points))
    fine = _charges(_response(_half_rc_nodes(sheet_resistance=1000.0), points))

    assert fine == pytest.approx(coarse, rel=0.01)


def test_response_of_a_point_mirrored_across_the_device_swaps_the_strips():
    # the strips and the load are symmetric about x = 100 um = l_x / 2
    my_d = _device(sheet_resistance=1000.0)

    near, mirrored = _response(my_d, [70.0, 130.0])

    np.testing.assert_allclose(
        near,
        mirrored[::-1],
        rtol=1e-3,
        atol=1e-4 * np.abs(near).max(),
    )


def test_strips_on_a_dielectric_over_a_grounded_layer_see_no_net_charge():
    # the layer held on ground at the RC node 19, the strips over 0.5 um of
    # oxide: the charge leaves through the ground and the strips see it pass
    my_d = _device(
        sheet_resistance=1000.0,
        grounded={"ring": [19, 19]},
        coupling={"thickness": 0.5, "permittivity": 3.9},
    )

    (waves,) = _response(my_d, [85.0])

    for wave in waves:
        assert np.abs(wave).max() > 0
        assert abs(wave.sum()) < 0.02 * np.abs(wave).sum()


def test_higher_sheet_resistance_keeps_more_of_the_signal_on_the_nearer_strip():
    # the wide strips of HPK in table 1 of arXiv:2407.09928: 500 um pitch,
    # 50 um of metal, 10 mm long, 50 um thick, 600 pF/mm^2 under the strips,
    # the layer of 400 or of 1600 Ohm a square. RC nodes of 50 um, 1.036 pF
    # each over 50 um of silicon; seven strips, the layer on ground at both
    # ends. A point 100 um from the middle of the strip s3, towards s4: the
    # more resistive the layer, the more of the amplitude stays on s3
    fractions = {}
    for ohm in (400.0, 1600.0):
        my_d = _build(
            {
                "read_ele_num": 70,
                "p_x": 50,
                "l_x": 3500,
                "l_y": 10000,
                "capacitance_pF": 1.036,
            },
            {
                "sheet_resistance": ohm,
                "grounded": {"near": [0, 0], "far": [69, 69]},
                "coupling": {"thickness": 0.0576, "permittivity": 3.9},
            },
            strips={f"s{k}": [10 * k + 5, 10 * k + 5] for k in range(7)},
        )
        (waves,) = _response(my_d, [1875.0])
        amplitude = np.abs(waves).max(axis=-1)
        fractions[ohm] = amplitude[3] / (amplitude[3] + amplitude[4])

    assert fractions[1600.0] > fractions[400.0] + 0.02
    assert fractions[400.0] > 0.5


@pytest.mark.parametrize("x_um", [201.0, -1.0])
def test_point_off_the_rc_nodes_of_the_layer_is_refused(x_um):
    my_d = _device(sheet_resistance=1000.0)

    with pytest.raises(ValueError, match="RC nodes of the layer"):
        shares(my_d, [x_um])
