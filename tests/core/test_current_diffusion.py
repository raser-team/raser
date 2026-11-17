"""Charge collected by diffusion alone in a pixel sensor without a field."""

from types import SimpleNamespace

import pytest

from raser.core import seeding
from raser.core.current.diffusion import ELEMENTARY_CHARGE, collect_by_diffusion

STEP = 50e-12  # s


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


def test_a_pair_made_inside_a_collection_region_arrives_in_the_bin_its_time_lies_in() -> None:
    # bins start at the first deposit and are STEP wide: 0.6 STEP lies in the first
    seeding.seed_generators(1)
    t0, current, _ = collect_by_diffusion(
        _pixels(), [1.0, 1.0], [[12.5, 12.5, 5.0, 0.0], [12.5, 12.5, 5.0, 0.6 * STEP]], 1e-9, STEP
    )

    arrived = current[0] * STEP / -ELEMENTARY_CHARGE
    assert t0 == 0.0
    assert arrived[0] == pytest.approx(2.0)
    assert arrived[1:].sum() == pytest.approx(0.0)
