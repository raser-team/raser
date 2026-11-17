"""Charge collected by diffusion alone in a pixel sensor without a field."""

from types import SimpleNamespace

import pytest

from raser.core import seeding
from raser.core.current.diffusion import ELEMENTARY_CHARGE, collect_by_diffusion, time_bin


def _pixels(**changes):
    """2 by 2 pixels of 25 um filling the device, collecting 10 um at their middle."""
    device = dict(
        is_pixel=True, det_name="pixels", material="Si", temperature=300.0,
        doping={"Donors": 0.0, "Acceptors": 1e13},
        l_x=50.0, l_y=50.0, l_z=10.0, p_x=25.0, p_y=25.0, x_ele_num=2, y_ele_num=2,
        e_width_x=10.0, e_width_y=10.0,
    )
    device.update(changes)
    return SimpleNamespace(**device)


def test_pixels_narrower_than_the_device_collect_where_they_are_centred() -> None:
    # 2 by 2 pixels of 10 um centred on a device 40 by 30 um: their middles at
    # x = 15 and 25 um, y = 10 and 20 um
    seeding.seed_generators(1)
    device = _pixels(l_x=40.0, l_y=30.0, p_x=10.0, p_y=10.0, e_width_x=4.0, e_width_y=4.0)

    _, _, charge = collect_by_diffusion(device, [1.0], [[25.0, 20.0, 5.0, 0.0]], 1e-12, 1e-12)

    assert charge / -ELEMENTARY_CHARGE == pytest.approx([0.0, 0.0, 0.0, 1.0])


def test_a_time_lies_in_the_bin_whose_left_edge_is_at_or_before_it() -> None:
    # t0 is the left edge of the first bin of 50 ps
    assert time_bin(0.6 * 50e-12, 0.0, 50e-12) == 0
    assert time_bin(0.0, 0.0, 50e-12) == 0
    # 29 steps after t0: the quotient is 28.999999999999996 in floating point
    assert time_bin(29 * 50e-12, 0.0, 50e-12) == 29
    assert time_bin(29 * 50e-12 - 1e-3 * 50e-12, 0.0, 50e-12) == 28
    # before t0, and far from the origin of time, where t0 + step rounds to t0
    assert time_bin(-0.4 * 50e-12, 0.0, 50e-12) == -1
    assert time_bin(1e6, 1e6, 50e-12) == 0


def test_pairs_made_inside_a_collection_region_arrive_in_the_bin_of_their_time() -> None:
    # the second deposit, 0.6 step after the first, is in the first bin; the
    # last bin of the window follows the bin of the last deposit
    seeding.seed_generators(1)
    t0, current, _ = collect_by_diffusion(
        _pixels(), [1.0, 1.0], [[12.5, 12.5, 5.0, 0.0], [12.5, 12.5, 5.0, 0.6 * 50e-12]], 1e-9, 50e-12
    )

    arrived = current[0] * 50e-12 / -ELEMENTARY_CHARGE
    assert t0 == 0.0
    assert current.shape[1] == 0 + 20 + 1
    assert arrived[0] == pytest.approx(2.0)


def test_the_window_reaches_as_far_after_the_last_deposit_as_after_the_first() -> None:
    # deposits at 0 and 3.4 steps: the bins run to the bin of the last, 3, and
    # the 20 steps of the window after it
    seeding.seed_generators(1)
    _, current, _ = collect_by_diffusion(
        _pixels(), [1.0, 1.0], [[12.5, 12.5, 5.0, 0.0], [12.5, 12.5, 5.0, 3.4 * 50e-12]], 1e-9, 50e-12
    )

    assert current.shape[1] == 3 + 20 + 1
    assert current[0, 3] * 50e-12 / -ELEMENTARY_CHARGE == pytest.approx(1.0)
