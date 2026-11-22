import numpy as np
import pytest

from raser.core.analysis.tracking import (
    Placement,
    SlotHits,
    TrackEvents,
    draw_residual,
    draw_track,
    residual_widths,
    track_events,
)

L = 1000.0  # lateral size of every device [um]
# the line of the tests: X = KX * Z + BX, Y = KY * Z + BY
KX, BX, KY, BY = 0.01, 100.0, -0.02, 50.0


def place(z, rotation=0, l_z=100.0, p_x=10.0, p_y=10.0, xy=(0.0, 0.0)):
    return Placement([xy[0], xy[1], z], rotation, L, L, l_z, p_x, p_y)


def hits_at(x, y, events=(1,), clusters=1):
    """Hits of an unrotated device at the origin, one per event, at the global (x, y)."""
    count = len(events)
    return SlotHits(
        np.array(events),
        np.full(count, clusters),
        np.broadcast_to(np.asarray(x, dtype=float) + L / 2, count).copy(),
        np.broadcast_to(np.asarray(y, dtype=float) + L / 2, count).copy(),
    )


def on_line(z_middle, shift_x=0.0):
    return hits_at(KX * z_middle + BX + shift_x, KY * z_middle + BY)


def telescope(shift_x=0.0, dut_l_z=100.0):
    """Three reference layers and a DUT on the line; the DUT is shifted along x."""
    placements = {
        "r0": place(0.0),
        "r1": place(10000.0),
        "r2": place(20000.0),
        "dut": place(30000.0, l_z=dut_l_z),
    }
    z_middle = {"r0": 50.0, "r1": 10050.0, "r2": 20050.0, "dut": 30000.0 + dut_l_z / 2}
    hits = {
        slot: on_line(z_middle[slot], shift_x if slot == "dut" else 0.0)
        for slot in placements
    }
    roles = {"r0": "reference", "r1": "reference", "r2": "reference", "dut": "dut"}
    return hits, placements, roles


def test_clusters_on_one_slanted_line_give_its_slope_and_intercept_and_no_residual() -> (
    None
):
    tracks = track_events(*telescope())

    columns = tracks.columns
    assert columns["selected"].tolist() == [True]
    assert columns["kx"][0] == pytest.approx(KX, abs=1e-12)
    assert columns["bx"][0] == pytest.approx(BX, abs=1e-9)
    assert columns["ky"][0] == pytest.approx(KY, abs=1e-12)
    assert columns["by"][0] == pytest.approx(BY, abs=1e-9)
    assert columns["residual_x"][0] == pytest.approx(0.0, abs=1e-9)
    assert columns["residual_y"][0] == pytest.approx(0.0, abs=1e-9)
    assert columns["chi2"][0] == pytest.approx(0.0, abs=1e-9)
    assert tracks.slots == ["r0", "r1", "r2", "dut"]


def test_dut_cluster_3_um_along_x_has_residual_minus_3_and_leaves_the_track_unchanged() -> (
    None
):
    tracks = track_events(*telescope(shift_x=3.0))

    columns = tracks.columns
    assert columns["residual_x"][0, 3] == pytest.approx(-3.0, abs=1e-9)
    assert columns["residual_x"][0, :3] == pytest.approx(0.0, abs=1e-9)
    assert columns["residual_y"][0] == pytest.approx(0.0, abs=1e-9)
    assert columns["kx"][0] == pytest.approx(KX, abs=1e-12)
    assert columns["bx"][0] == pytest.approx(BX, abs=1e-9)


@pytest.mark.parametrize(
    "rotation, expected",
    [
        (90, lambda a, b: (1000.0 - b, 2000.0 + a)),
        (180, lambda a, b: (1000.0 - a, 2000.0 - b)),
        (270, lambda a, b: (1000.0 + b, 2000.0 - a)),
    ],
)
def test_cluster_of_a_rotated_layer_lies_where_the_quarter_turns_put_it(
    rotation, expected
) -> None:
    a, b = 30.0, 70.0
    placements = {
        "r0": place(0.0),
        "r1": place(10000.0),
        "turned": Placement(
            [1000.0, 2000.0, 20000.0], rotation, 400.0, 600.0, 100.0, 10.0, 10.0
        ),
    }
    hits = {
        "r0": hits_at(0.0, 0.0),
        "r1": hits_at(0.0, 0.0),
        "turned": SlotHits(
            np.array([1]), np.array([1]), np.array([200.0 + a]), np.array([300.0 + b])
        ),
    }
    roles = {"r0": "reference", "r1": "reference", "turned": "dut"}

    tracks = track_events(hits, placements, roles)

    assert (tracks.columns["x"][0, 2], tracks.columns["y"][0, 2]) == pytest.approx(
        expected(a, b), abs=1e-9
    )


def test_track_table_z_is_the_middle_of_the_device_so_residuals_are_taken_there() -> (
    None
):
    # the DUT is 500 um thick; on the line at its middle plane it has no residual,
    # and a Z at its front face would give one of KX * 250 = 2.5 um
    tracks = track_events(*telescope(dut_l_z=500.0))

    assert tracks.z.tolist() == [50.0, 10050.0, 20050.0, 30250.0]
    assert tracks.columns["residual_x"][0, 3] == pytest.approx(0.0, abs=1e-9)
    assert tracks.columns["residual_y"][0, 3] == pytest.approx(0.0, abs=1e-9)


def test_event_with_a_slot_missing_or_with_two_clusters_is_not_selected_and_the_others_are() -> (
    None
):
    hits, placements, roles = telescope()
    for slot in ("r0", "r1", "r2"):
        hits[slot] = SlotHits(
            np.array([1, 2, 3, 4]),
            np.ones(4, dtype=int),
            np.full(4, hits[slot].cluster_x[0]),
            np.full(4, hits[slot].cluster_y[0]),
        )
    # no record for event 2, two clusters in event 3
    hits["dut"] = SlotHits(
        np.array([1, 3, 4]),
        np.array([1, 2, 1]),
        np.array([hits["dut"].cluster_x[0], np.nan, hits["dut"].cluster_x[0]]),
        np.array([hits["dut"].cluster_y[0], np.nan, hits["dut"].cluster_y[0]]),
    )

    columns = track_events(hits, placements, roles).columns

    assert columns["event"].tolist() == [1, 2, 3, 4]
    assert columns["selected"].tolist() == [True, False, False, True]
    for name in ("kx", "bx", "ky", "by", "chi2"):
        assert np.isnan(columns[name][[1, 2]]).all()
        assert columns[name][[0, 3]] == pytest.approx(columns[name][0], abs=1e-9)
    assert np.isnan(columns["residual_x"][[1, 2]]).all()
    assert np.isnan(columns["residual_y"][[1, 2]]).all()
    assert np.isnan(columns["x"][[1, 2], 3]).all()
    assert np.isfinite(columns["x"][[1, 2], :3]).all()
    assert columns["residual_x"][[0, 3]] == pytest.approx(0.0, abs=1e-9)


def three_references(local_xy, rotations=(0, 0, 0)):
    """Three reference layers at Z = -1000, 0, 1000 at the origin, p_x = 10 and
    p_y = 20, the middle one turned by rotations[1]; local_xy are the global
    positions the clusters are given for."""
    z_middle = (-1000.0, 0.0, 1000.0)
    placements = {
        f"r{j}": Placement([0.0, 0.0, z], rotations[j], L, L, 0.0, 10.0, 20.0)
        for j, z in enumerate(z_middle)
    }
    hits = {}
    for j, (x, y) in enumerate(local_xy):
        # the inverse of the quarter turn about the centre, for the local cluster
        cos, sin = {0: (1, 0), 90: (0, 1), 180: (-1, 0), 270: (0, -1)}[rotations[j]]
        local = (cos * x + sin * y + L / 2, -sin * x + cos * y + L / 2)
        hits[f"r{j}"] = SlotHits(
            np.array([1]), np.array([1]), np.array([local[0]]), np.array([local[1]])
        )
    return hits, placements, dict.fromkeys(placements, "reference")


def test_chi2_is_the_residuals_over_the_uniform_spread_of_the_pitch() -> None:
    # X = 0, 6, 0 gives the flat line 2 and residuals 2, -4, 2; Y = 0, 3, 0 gives 1 and 1, -2, 1
    hits, placements, roles = three_references([(0.0, 0.0), (6.0, 3.0), (0.0, 0.0)])
    hits["dut"] = SlotHits(
        np.array([1]), np.array([1]), np.array([L / 2 + 900.0]), np.array([L / 2])
    )
    placements["dut"] = Placement([0.0, 0.0, 2000.0], 0, L, L, 0.0, 10.0, 20.0)
    roles["dut"] = "dut"

    chi2 = track_events(hits, placements, roles).columns["chi2"][0]

    # pitch 10 along x: 24 / (100 / 12); pitch 20 along y: 6 / (400 / 12); the DUT adds nothing
    assert chi2 == pytest.approx(24 / (100 / 12) + 6 / (400 / 12), abs=1e-9)


def test_chi2_of_a_layer_turned_a_quarter_uses_the_pitches_swapped() -> None:
    hits, placements, roles = three_references(
        [(0.0, 0.0), (6.0, 3.0), (0.0, 0.0)], rotations=(0, 90, 0)
    )

    tracks = track_events(hits, placements, roles)

    assert tracks.columns["x"][0].tolist() == pytest.approx([0.0, 6.0, 0.0], abs=1e-9)
    # the turned layer has pitch 20 along x and 10 along y
    expected = (
        (2**2 + 2**2) / (100 / 12)
        + 4**2 / (400 / 12)
        + (1 + 1) / (400 / 12)
        + 2**2 / (100 / 12)
    )
    assert tracks.columns["chi2"][0] == pytest.approx(expected, abs=1e-9)


def test_one_reference_layer_is_not_enough_for_a_track() -> None:
    hits, placements, roles = telescope()
    roles["r1"] = roles["r2"] = "dut"
    with pytest.raises(
        ValueError, match="a track needs reference layers at two or more z"
    ):
        track_events(hits, placements, roles)


def test_reference_layers_at_one_z_do_not_give_a_track() -> None:
    hits, placements, roles = telescope()
    placements["r1"] = place(0.0)
    placements["r2"] = place(0.0)
    with pytest.raises(
        ValueError, match="a track needs reference layers at two or more z"
    ):
        track_events(hits, placements, roles)


def test_slot_names_that_differ_between_the_three_dictionaries_are_refused() -> None:
    hits, placements, roles = telescope()
    del hits["dut"]
    with pytest.raises(
        ValueError, match="the slots of hits, placements and roles differ"
    ):
        track_events(hits, placements, roles)


def test_rotation_that_is_not_a_quarter_turn_is_refused() -> None:
    hits, placements, roles = telescope()
    placements["dut"] = Placement([0.0, 0.0, 30000.0], 45, L, L, 100.0, 10.0, 10.0)
    with pytest.raises(ValueError, match="rotation_z 45"):
        track_events(hits, placements, roles)


def gaussian_tracks(seed, count=5000, sigma=4.0, unselected=0):
    """Tracks of slots r0, r1 (reference) and dut whose DUT residuals are Gaussian."""
    rng = np.random.default_rng(seed)
    total = count + unselected
    selected = np.arange(total) < count
    residual = np.full((total, 3), np.nan)
    residual[selected, 2] = rng.normal(0.0, sigma, count)
    return TrackEvents(
        ["r0", "r1", "dut"],
        ["reference", "reference", "dut"],
        np.array([0.0, 10000.0, 20000.0]),
        {
            "event": np.arange(total),
            "selected": selected,
            "x": np.zeros((total, 3)),
            "y": np.zeros((total, 3)),
            "kx": np.where(selected, 0.0, np.nan),
            "bx": np.where(selected, 0.0, np.nan),
            "ky": np.where(selected, 0.0, np.nan),
            "by": np.where(selected, 0.0, np.nan),
            "chi2": np.where(selected, 1.0, np.nan),
            "residual_x": residual,
            "residual_y": residual.copy(),
        },
    )


def test_core_width_of_the_residuals_of_two_jobs_is_the_sigma_of_their_gaussian() -> (
    None
):
    widths = residual_widths([gaussian_tracks(1, unselected=50), gaussian_tracks(2)])

    assert list(widths) == ["dut"]
    for axis in ("x", "y"):
        result = widths["dut"][axis]
        assert result["events"] == 10000
        assert result["sigma"] == pytest.approx(4.0, abs=5 * result["sigma_error"])


def test_fewer_than_20_selected_events_give_an_error_instead_of_a_width() -> None:
    widths = residual_widths(
        [gaussian_tracks(1, count=10, unselected=100), gaussian_tracks(2, count=9)]
    )

    assert widths["dut"]["x"]["events"] == 19
    assert "19" in widths["dut"]["x"]["error"]
    assert "sigma" not in widths["dut"]["y"]


def test_jobs_with_other_slots_or_roles_have_no_common_widths() -> None:
    other = gaussian_tracks(2)
    other.roles = ["reference", "dut", "dut"]
    with pytest.raises(ValueError):
        residual_widths([gaussian_tracks(1), other])


@pytest.mark.root
def test_track_is_written_as_a_png(tmp_path) -> None:
    tracks = track_events(*telescope(shift_x=3.0))

    png = draw_track(tracks, 1, tmp_path)

    assert png.name == "track_1.png"
    assert png.stat().st_size > 0


@pytest.mark.root
def test_residual_is_written_as_a_png_with_and_without_a_fit(tmp_path) -> None:
    tracks = [gaussian_tracks(1), gaussian_tracks(2)]
    widths = residual_widths(tracks)
    widths["dut"]["y"] = {"events": 10000, "error": "stand-in for too few values"}

    png = draw_residual(tracks, "dut", widths["dut"], tmp_path)

    assert png.name == "residual_dut.png"
    assert png.stat().st_size > 0
