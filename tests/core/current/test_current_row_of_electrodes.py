from __future__ import annotations

from types import SimpleNamespace

import pytest

from raser.core.current.cal_current import CalCurrent


def test_the_electrodes_near_a_start_are_those_its_weighting_potential_reaches() -> None:
    current = object.__new__(CalCurrent)
    current.read_out_contact = [{"name": "top"}]
    # 16 strips at a pitch of 50 um, the first from 100 um
    device = SimpleNamespace(l_x=1000.0, p_x=50.0, x_ele_num=16, l_y=10.0, p_y=10.0, y_ele_num=1)
    # the weighting potential is on five cells from 0, its strip on the middle one
    field = SimpleNamespace(cells_either_side=2)

    near = current.electrodes_near(470.0, 5.0, device, field)

    assert [number for number, _, _ in near] == [5, 6, 7, 8, 9]
    for number, in_field, offset in near:
        centre = 100.0 + (number + 0.5) * 50.0
        assert in_field == 0
        assert centre - offset[0] == pytest.approx(125.0)
        assert offset[1] == 0.0
    # the row of the device ends before that of the potential
    assert [number for number, _, _ in current.electrodes_near(110.0, 5.0, device, field)] == [0, 1, 2]
