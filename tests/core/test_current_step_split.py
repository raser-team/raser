"""The pairs of a particle's step, split where the step crosses the edge of a conducting region."""

import pytest

from raser.core.current.cal_current import split_at_conductor_edges


def _layer(low, high):
    """The device conducts between z = low and high um."""
    return lambda x, y, z: low <= z < high


def test_a_step_that_crosses_no_edge_keeps_its_middle_and_its_pairs() -> None:
    parts = split_at_conductor_edges((5.0, 5.0, 10.0), (5.0, 5.0, 11.0), 80.0, _layer(0.0, 1.0))

    assert parts == [(5.0, 5.0, 11.0, 80.0)]


def test_a_step_into_a_conducting_layer_gives_each_side_its_share_of_the_pairs() -> None:
    # from z = 2 to 0 um across the edge at 1 um: half the length on each side
    parts = split_at_conductor_edges((5.0, 5.0, 2.0), (5.0, 5.0, 1.0), 80.0, _layer(0.0, 1.0))

    assert len(parts) == 2
    assert parts[0] == pytest.approx((5.0, 5.0, 1.5, 40.0), abs=0.01)
    assert parts[1] == pytest.approx((5.0, 5.0, 0.5, 40.0), abs=0.01)


def test_a_step_through_a_layer_thinner_than_itself_is_split_on_both_edges() -> None:
    # both ends outside the layer at 1.0 - 1.3 um; 2 um long: 0.5, 0.3 and 1.2 um
    parts = split_at_conductor_edges((5.0, 5.0, 0.5), (5.0, 5.0, 1.5), 100.0, _layer(1.0, 1.3))

    assert len(parts) == 3
    assert [part[3] for part in parts] == pytest.approx([25.0, 15.0, 60.0], abs=0.01)
    assert [part[2] for part in parts] == pytest.approx([0.75, 1.15, 1.9], abs=0.01)


def test_a_slanted_step_is_split_along_its_length() -> None:
    # from (0, 0, 2) to (3, 0, -2): 5 um long, crossing z = 1 a quarter of the way
    parts = split_at_conductor_edges((0.0, 0.0, 2.0), (1.5, 0.0, 0.0), 40.0, _layer(-5.0, 1.0))

    assert len(parts) == 2
    assert parts[0] == pytest.approx((0.375, 0.0, 1.5, 10.0), abs=0.01)
    assert parts[1] == pytest.approx((1.875, 0.0, -0.5, 30.0), abs=0.01)
