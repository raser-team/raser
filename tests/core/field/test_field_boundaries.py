from __future__ import annotations

import numpy as np
import pytest

from raser.core.field.devsim_draw import doping_boundaries


def test_pin_steps_give_the_two_junction_depths():
    depth = np.arange(0, 150.5, 0.5)
    doping = np.where(depth < 1, 1e19, np.where(depth < 50, -5e12, -1e18))
    found = doping_boundaries(depth, doping)
    assert len(found) == 2
    assert found[0] == pytest.approx(1, abs=0.5)
    assert found[1] == pytest.approx(50, abs=0.5)


def test_smooth_change_gives_no_boundary():
    depth = np.arange(0, 20.0)
    doping = 1e12 * 1.5 ** depth
    assert doping_boundaries(depth, doping) == []


def test_zero_segment_is_bounded_on_both_sides():
    depth = np.arange(0, 10.0)
    doping = np.array([1e15] * 3 + [0.0] * 4 + [1e15] * 3)
    found = doping_boundaries(depth, doping)
    assert found == pytest.approx([2.5, 6.5])


def test_all_zero_gives_no_boundary():
    assert doping_boundaries([0.0, 1.0, 2.0], [0.0, 0.0, 0.0]) == []


def test_jumps_closer_than_half_a_micron_merge_into_their_mean():
    depth = np.array([0.0, 0.3, 0.6, 0.9])
    doping = np.array([1e12, 1e15, -1e18, -1e18])
    assert doping_boundaries(depth, doping) == pytest.approx([0.3])


def test_far_apart_jumps_stay_separate():
    depth = np.array([0.0, 1.0, 2.0, 3.0])
    doping = np.array([1e12, 1e15, 1e15, 1e18])
    assert len(doping_boundaries(depth, doping)) == 2


def test_threshold_lies_between_a_factor_of_eight_and_twelve():
    depth = np.array([0.0, 1.0])
    assert doping_boundaries(depth, [1e15, 8e15]) == []
    assert doping_boundaries(depth, [1e15, 1.2e16]) == pytest.approx([0.5])
    assert doping_boundaries(depth, [-1e15, 1.2e16]) == pytest.approx([0.5])
