"""Charge collected by diffusion alone in a pixel sensor without a field."""

from types import SimpleNamespace

import pytest

from raser.core import seeding
from raser.core.current.diffusion import ELEMENTARY_CHARGE, collect_by_diffusion


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
    # two pixels of 10 um centred on a device 40 um wide: their middles at 15 and 25 um
    seeding.seed_generators(1)
    device = _pixels(l_x=40.0, l_y=10.0, p_x=10.0, p_y=10.0, x_ele_num=2, y_ele_num=1, e_width_x=4.0, e_width_y=4.0)

    _, _, charge = collect_by_diffusion(device, [1.0], [[25.0, 5.0, 5.0, 0.0]], 1e-12, 1e-12)

    assert charge / -ELEMENTARY_CHARGE == pytest.approx([0.0, 1.0])
