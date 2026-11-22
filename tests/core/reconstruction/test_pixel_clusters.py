from types import SimpleNamespace

import numpy as np
import pytest

from raser.core.deposit.deposits import Deposits, EventDeposits
from raser.core.reconstruction.event_table import (
    EventTable,
    read_event_table,
    write_event_table,
)
from raser.core.reconstruction.pixel_clusters import (
    CLUSTER_COLUMNS,
    draw_hitmap,
    fired_from_deposits,
    fired_from_table,
    pixel_cluster_columns,
    pixel_clusters,
    table_from_deposits,
)

DEVICE = SimpleNamespace(
    p_x=25.0, p_y=50.0, l_x=100.0, l_y=200.0, l_z=50.0, x_ele_num=4, y_ele_num=4
)


def deposit_event(event, steps):
    """steps: (detector, x, y, z, pairs)"""
    names, x, y, z, pairs = zip(*steps)
    return EventDeposits(
        event,
        list(names),
        list(x),
        list(y),
        list(z),
        [0.0] * len(steps),
        [1.0] * len(steps),
        list(pairs),
    )


def test_two_pixels_touching_at_a_corner_are_one_cluster_at_the_mean_of_their_centres() -> (
    None
):
    fired, weight = np.zeros((4, 4), dtype=bool), np.zeros((4, 4))
    fired[0, 0] = fired[1, 1] = True
    weight[0, 0] = weight[1, 1] = 1.0

    ((x_c, y_c, n_c, seed),) = pixel_clusters(fired, weight, 1.0, 25.0, 50.0)

    # centres (12.5, 25) and (37.5, 75)
    assert x_c == pytest.approx(25.0, abs=1e-9)
    assert y_c == pytest.approx(50.0, abs=1e-9)
    assert n_c == 2
    assert seed == 0  # equal weights: the lower electrode index


def test_pixels_a_pixel_apart_are_two_clusters_in_ascending_seed_electrode() -> None:
    fired = np.zeros((2, 3), dtype=bool)
    weight = np.zeros((2, 3))
    # the cluster met first has its seed (1, 0), k = 3; the other one (0, 2), k = 2
    for (i_x, i_y), value in {(0, 0): 1.0, (1, 0): 5.0, (0, 2): 3.0}.items():
        fired[i_x, i_y] = True
        weight[i_x, i_y] = value

    found = pixel_clusters(fired, weight, 1.0, 25.0, 50.0)

    assert [(n_c, seed) for _, _, n_c, seed in found] == [(1, 2), (2, 3)]
    assert found[0][:2] == pytest.approx((12.5, 125.0), abs=1e-9)


def test_fired_pixels_without_a_pixel_at_the_seed_threshold_are_no_cluster() -> None:
    fired = np.zeros((4, 4), dtype=bool)
    weight = np.zeros((4, 4))
    for (i_x, i_y), value in {
        (0, 0): 1.9,
        (0, 1): 1.5,
        (3, 3): 1.0,
        (3, 2): 2.0,
    }.items():
        fired[i_x, i_y] = True
        weight[i_x, i_y] = value

    found = pixel_clusters(fired, weight, 2.0, 25.0, 50.0)

    # the first group stays below 2; the second counts whole, its pixel below 2 included
    assert [(n_c, seed) for _, _, n_c, seed in found] == [(2, 14)]


def test_seed_is_the_pixel_of_the_largest_weight_numbered_by_n_y() -> None:
    fired = np.zeros((3, 2), dtype=bool)
    weight = np.zeros((3, 2))
    for (i_x, i_y), value in {(1, 1): 1.0, (2, 1): 9.0, (2, 0): 4.0}.items():
        fired[i_x, i_y] = True
        weight[i_x, i_y] = value

    ((_, _, n_c, seed),) = pixel_clusters(fired, weight, 1.0, 25.0, 50.0)

    assert (n_c, seed) == (3, 2 * 2 + 1)


def test_columns_of_an_event_with_two_clusters_have_no_position_and_no_seed() -> None:
    fired = np.zeros((3, 4, 4), dtype=bool)
    weight = np.zeros((3, 4, 4))
    fired[0, 2, 1] = True  # one cluster of one pixel
    weight[0, 2, 1] = 3.0
    fired[1, 0, 0] = fired[1, 3, 3] = True  # two
    weight[1, 0, 0] = weight[1, 3, 3] = 3.0  # and none in event 2

    columns = pixel_cluster_columns(fired, weight, 1.0, 25.0, 50.0)

    assert set(columns) == set(CLUSTER_COLUMNS)
    assert columns["clusters"].tolist() == [1, 2, 0]
    assert columns["cluster_x"][0] == pytest.approx(62.5, abs=1e-9)
    assert columns["cluster_y"][0] == pytest.approx(75.0, abs=1e-9)
    assert columns["cluster_pixels"].tolist() == [1, 0, 0]
    assert columns["cluster_seed"].tolist() == [2 * 4 + 1, -1, -1]
    assert np.isnan(columns["cluster_x"][1:]).all()
    assert np.isnan(columns["cluster_y"][1:]).all()
    assert (
        columns["clusters"].dtype
        == columns["cluster_pixels"].dtype
        == columns["cluster_seed"].dtype
        == np.int64
    )


def test_electrode_four_of_a_2_by_3_array_is_pixel_one_one() -> None:
    amplitude = np.array([[0.0, 0.0, 0.0, 0.0, 0.7, 0.0]])
    table = EventTable(
        [f"e{k}" for k in range(6)],
        0.01,
        0.02,
        (),
        ["rising"] * 6,
        {"event": np.array([0]), "above": amplitude > 0, "amplitude": amplitude},
    )

    fired, weight, seed_threshold = fired_from_table(table, 2, 3)

    assert fired.shape == weight.shape == (1, 2, 3)
    assert np.argwhere(fired[0]).tolist() == [[1, 1]]
    assert weight[0, 1, 1] == pytest.approx(0.7, abs=1e-12)
    assert seed_threshold == 0.02
    with pytest.raises(ValueError, match="6 electrodes.*2 x 2 array has 4"):
        fired_from_table(table, 2, 2)


def test_step_at_30_80_lies_in_pixel_one_one_and_only_steps_of_the_slot_with_pairs_count() -> (
    None
):
    deposits = Deposits(
        2,
        None,
        None,
        [
            deposit_event(
                7,
                [
                    ("a", 30.0, 80.0, 10.0, 100.0),
                    ("a", 40.0, 99.0, 20.0, 50.0),  # same pixel: the pairs add
                    ("b", 80.0, 160.0, 10.0, 9.0),  # another slot
                    ("a", 80.0, 160.0, 10.0, 0.0),  # no pairs
                    ("a", -1.0, 80.0, 10.0, 7.0),  # outside the device
                    (
                        "a",
                        100.0,
                        80.0,
                        10.0,
                        7.0,
                    ),  # on the far edge: beyond the last pixel
                ],
            ),
            deposit_event(9, [("b", 30.0, 80.0, 10.0, 5.0)]),
        ],
    )

    events, fired, weight, seed_threshold = fired_from_deposits(deposits, "a", DEVICE)

    assert events.tolist() == [7, 9]
    assert events.dtype == np.int64
    assert np.argwhere(fired[0]).tolist() == [[1, 1]]
    assert weight[0, 1, 1] == pytest.approx(150.0, abs=1e-9)
    assert weight[0].sum() == pytest.approx(150.0, abs=1e-9)
    assert not fired[1].any()
    assert seed_threshold == 0.0


def test_event_table_of_deposits_is_read_back_from_its_file_as_written(
    tmp_path,
) -> None:
    deposits = Deposits(
        3,
        None,
        None,
        [
            deposit_event(1, [("a", 30.0, 80.0, 10.0, 100.0)]),
            deposit_event(
                2, [("a", 10.0, 10.0, 10.0, 5.0), ("a", 90.0, 190.0, 10.0, 5.0)]
            ),
            deposit_event(3, [("b", 30.0, 80.0, 10.0, 100.0)]),
        ],
    )
    table = table_from_deposits(deposits, "a", DEVICE)
    assert table.columns["selected"].tolist() == [True, True, False]
    assert table.columns["clusters"].tolist() == [1, 2, 0]

    write_event_table(tmp_path / "reconstruction.h5", table)
    back = read_event_table(tmp_path / "reconstruction.h5")

    assert (
        set(back.columns)
        == set(table.columns)
        == {"event", "selected", *CLUSTER_COLUMNS}
    )
    for name, values in table.columns.items():
        assert back.columns[name].dtype == values.dtype
        np.testing.assert_array_equal(back.columns[name], values)
    assert (back.electrodes, back.edges, back.fractions) == ([], [], ())


@pytest.mark.root
def test_hitmap_is_written_as_a_png(tmp_path) -> None:
    deposits = Deposits(
        1, None, None, [deposit_event(1, [("a", 30.0, 80.0, 10.0, 100.0)])]
    )
    table = table_from_deposits(deposits, "a", DEVICE)

    png = draw_hitmap(table, DEVICE, tmp_path, "a")

    assert png.name == "hitmap_a.png"
    assert png.stat().st_size > 0
    assert draw_hitmap(table, DEVICE, tmp_path).name == "hitmap.png"
