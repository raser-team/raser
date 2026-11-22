from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from raser.core.current.cal_current import CalCurrent
from raser.core.current.cal_current import spread_over_bins
from raser.core.current.drift import induced_charges

E0 = 1.602176634e-19
CARRIERS = 100.0
DEPTH_UM = 50.0
T_BIN = 1e-10


class _Slab:
    """The weighting potential of a slab 50 um deep: 1 at the top surface, 0 at the back,
    the same for every electrode asked for."""

    cells_either_side = 0

    def get_w_p(self, x, y, z, electrode):
        return 1.0 - z / DEPTH_UM


class _Pair:
    """Two electrodes facing each other: 1 - z/50 on the first, z/50 on the second."""

    cells_either_side = 0

    def get_w_p(self, x, y, z, electrode):
        return 1.0 - z / DEPTH_UM if electrode == 0 else z / DEPTH_UM


def _layer_device() -> SimpleNamespace:
    # 4 RC nodes along x at a pitch of 50 um, centred at 25, 75, 125 and 175 um; one along y
    return SimpleNamespace(
        resistive_layer={"contact": "top"},
        l_x=200.0, p_x=50.0, x_ele_num=4, l_y=50.0, p_y=50.0, y_ele_num=1, read_ele_num=4,
    )  # fmt: skip


def _plain_device(electrodes: int) -> SimpleNamespace:
    return SimpleNamespace(
        l_x=200.0, p_x=200.0 / electrodes, x_ele_num=electrodes, l_y=50.0, p_y=50.0, y_ele_num=1,
        read_ele_num=electrodes,
    )  # fmt: skip


def _current(read_out_contact: list[dict], read_ele_num: int) -> CalCurrent:
    current = object.__new__(CalCurrent)
    current.read_out_contact = read_out_contact
    current.read_ele_num = read_ele_num
    current.n_bin = 20
    current.t_start = 0.0
    current.t_end = 20 * T_BIN
    current.t_bin = T_BIN
    return current


def _system(path: np.ndarray) -> SimpleNamespace:
    return SimpleNamespace(carriers=[CARRIERS], remaining=[None], paths=[path])


def _path(x_um: list[float], z_um: list[float], step_s: float = 0.7e-10) -> np.ndarray:
    return np.array(
        [[x, 25.0, z, k * step_s] for k, (x, z) in enumerate(zip(x_um, z_um))]
    )


def _charge_on_cells(bins: np.ndarray) -> np.ndarray:
    return bins.sum(axis=1) * T_BIN


def test_the_nodes_of_a_resistive_layer_together_take_what_one_plane_electrode_takes() -> (
    None
):
    path = _path([100.0] * 5, [0.0, 10.0, 20.0, 30.0, 40.0])
    layer = _current([{"name": "node"}], 4)
    plane = _current([{"name": "top"}], 1)

    cells = layer.binned(_layer_device(), _Slab(), _system(path))
    one = plane.binned(_plain_device(1), _Slab(), _system(path))

    assert cells.shape == (4, 22)
    assert np.abs(one).max() > 0
    np.testing.assert_allclose(cells.sum(axis=0), one[0], rtol=1e-12, atol=0)


@pytest.mark.parametrize(
    ("x_um", "to_cells"),
    [
        (25.0, (1.0, 0.0)),  # over the middle of the first node
        (50.0, (0.5, 0.5)),  # on the edge between the first two
        (
            37.5,
            (0.75, 0.25),
        ),  # a quarter of the way from the first middle to the second
    ],
)
def test_a_vertical_path_shares_its_charge_by_its_distance_to_the_middles_of_the_nodes(
    x_um: float, to_cells: tuple[float, float]
) -> None:
    path = _path([x_um] * 5, [0.0, 10.0, 20.0, 30.0, 40.0])
    # 100 carriers across a fall of 0.8 of the weighting potential
    total = CARRIERS * E0 * (-0.8)

    cells = _current([{"name": "node"}], 4).binned(
        _layer_device(), _Slab(), _system(path)
    )

    charge = _charge_on_cells(cells)
    assert charge[0] == pytest.approx(to_cells[0] * total, rel=1e-9, abs=0)
    assert charge[1] == pytest.approx(to_cells[1] * total, rel=1e-9, abs=0)
    assert charge[2:] == pytest.approx(0.0, abs=1e-30)


def test_a_slanting_path_gives_each_node_the_planar_charge_of_the_steps_over_it() -> (
    None
):
    x_um = [20.0, 45.0, 70.0, 95.0, 120.0, 145.0]
    path = _path(x_um, [0.0, 8.0, 16.0, 24.0, 32.0, 40.0])
    # each step falls 8 um of 50: 0.16 of the potential, 100 carriers
    step = CARRIERS * E0 * (-0.16)
    # The middles of the steps lie at 32.5, 57.5, 82.5, 107.5 and 132.5 um. A node takes
    # 1 - d/50 of what lies d um from its middle, 25, 75, 125 or 175 um, and none from
    # further than 50 um:
    # 32.5: 0.85 to node 0, 0.15 to node 1       57.5: 0.35 and 0.65
    # 82.5: 0.85 to node 1, 0.15 to node 2       107.5: 0.35 and 0.65
    # 132.5: 0.85 to node 2, 0.15 to node 3
    expected_parts = [0.85 + 0.35, 0.15 + 0.65 + 0.85 + 0.35, 0.15 + 0.65 + 0.85, 0.15]

    cells = _current([{"name": "node"}], 4).binned(
        _layer_device(), _Slab(), _system(path)
    )

    charge = _charge_on_cells(cells)
    assert charge == pytest.approx(np.array(expected_parts) * step, rel=1e-9, abs=0)
    assert charge.sum() == pytest.approx(5 * step, rel=1e-9, abs=0)


def test_a_step_whose_middle_is_off_the_nodes_of_the_layer_is_an_error() -> None:
    # the nodes reach from 0 to 200 um; the middle of this step lies at 210 um
    path = _path([190.0, 230.0], [0.0, 10.0])

    with pytest.raises(ValueError, match="RC nodes of the layer"):
        _current([{"name": "node"}], 4).binned(_layer_device(), _Slab(), _system(path))


def test_a_device_without_a_resistive_layer_gets_the_charge_of_each_of_its_electrodes() -> (
    None
):
    path = _path([60.0, 70.0, 80.0, 90.0], [0.0, 10.0, 20.0, 40.0])
    device = _plain_device(2)
    device.read_ele_num = 2
    current = _current([{"name": "a"}, {"name": "b"}], 2)
    field = _Pair()

    bins = current.binned(device, field, _system(path))

    # by hand: each electrode takes the planar charge of each step, in the bins its time covers
    expected = np.zeros((2, current.n_bin + 2))
    for electrode in range(2):
        for k in range(3):
            value = CARRIERS * E0 * (field.get_w_p(0, 0, path[k + 1, 2], electrode)
                                     - field.get_w_p(0, 0, path[k, 2], electrode))  # fmt: skip
            spread_over_bins(
                expected[electrode],
                value / T_BIN,
                path[k, 3],
                path[k + 1, 3],
                0.0,
                T_BIN,
            )
    np.testing.assert_allclose(bins, expected, rtol=1e-12, atol=0)
    assert induced_charges(path, CARRIERS, field, 0).sum() == pytest.approx(
        -induced_charges(path, CARRIERS, field, 1).sum()
    )
