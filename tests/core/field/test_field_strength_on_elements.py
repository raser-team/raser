import numpy as np
import pytest

from raser.core.field.devsim_draw import boundaries_on_line
from raser.core.field.devsim_draw import field_strength_at_nodes
from raser.core.field.devsim_draw import interpolate_on_elements
from raser.core.field.devsim_draw import profile_positions
from raser.core.field.devsim_draw import profile_title
from raser.core.field.devsim_draw import value_limits


def _square(n):
    """The unit square with n x n nodes; each small square is cut into two
    triangles, along the one diagonal or the other in a checkerboard."""
    grid = np.linspace(0.0, 1.0, n)
    xx, yy = np.meshgrid(grid, grid, indexing="ij")
    points = np.column_stack([xx.ravel(), yy.ravel()])
    index = np.arange(n * n).reshape(n, n)
    elements = []
    for i in range(n - 1):
        for j in range(n - 1):
            a, b, c, d = (
                index[i, j],
                index[i + 1, j],
                index[i + 1, j + 1],
                index[i, j + 1],
            )
            if (i + j) % 2 == 0:
                elements += [[a, b, c], [a, c, d]]
            else:
                elements += [[a, b, d], [b, c, d]]
    return points, np.array(elements)


def _cube(n):
    """The unit cube with n^3 nodes; each small cube is cut into 6 tetrahedra
    around its diagonal from corner 000 to corner 111."""
    grid = np.linspace(0.0, 1.0, n)
    xx, yy, zz = np.meshgrid(grid, grid, grid, indexing="ij")
    points = np.column_stack([xx.ravel(), yy.ravel(), zz.ravel()])
    index = np.arange(n**3).reshape(n, n, n)
    paths = [(0, 1, 2), (0, 2, 1), (1, 0, 2), (1, 2, 0), (2, 0, 1), (2, 1, 0)]
    elements = []
    for i in range(n - 1):
        for j in range(n - 1):
            for k in range(n - 1):
                for path in paths:
                    corner = np.array([i, j, k])
                    nodes = [index[tuple(corner)]]
                    for axis in path:
                        corner[axis] += 1
                        nodes.append(index[tuple(corner)])
                    elements.append(nodes)
    return points, np.array(elements)


def test_gradient_of_a_plane_is_exact_on_every_node_of_a_mixed_triangulation():
    points, elements = _square(6)
    potential = 3 * points[:, 0] - 4 * points[:, 1]
    assert field_strength_at_nodes(points, elements, potential) == pytest.approx(
        5, rel=1e-12
    )


def test_gradient_of_a_plane_is_exact_on_every_node_of_a_tetrahedral_mesh():
    points, elements = _cube(4)
    potential = points[:, 0] + 2 * points[:, 1] + 2 * points[:, 2]
    assert field_strength_at_nodes(points, elements, potential) == pytest.approx(
        3, rel=1e-12
    )


def test_gradient_of_a_curved_potential_follows_the_field_inside():
    points, elements = _square(21)
    strength = field_strength_at_nodes(points, elements, points[:, 0] ** 2)
    inside = (
        (points[:, 0] > 0)
        & (points[:, 0] < 1)
        & (points[:, 1] > 0)
        & (points[:, 1] < 1)
    )
    assert np.abs(strength[inside] - 2 * points[inside, 0]).max() < 0.06


def test_a_node_of_no_element_has_no_field():
    points, elements = _square(3)
    points = np.vstack([points, [[5.0, 5.0]]])
    strength = field_strength_at_nodes(points, elements, np.zeros(len(points)))
    assert np.isnan(strength[-1]) and not np.isnan(strength[:-1]).any()


def test_interpolation_reproduces_a_plane_inside_and_is_nan_outside():
    points, elements = _square(6)
    potential = 3 * points[:, 0] - 4 * points[:, 1] + 1
    inside = np.random.default_rng(1).uniform(0.0, 1.0, (50, 2))
    assert interpolate_on_elements(
        points, elements, potential, inside
    ) == pytest.approx(3 * inside[:, 0] - 4 * inside[:, 1] + 1, rel=1e-12)
    outside = np.array([[1.2, 0.5], [0.5, -0.1], [-1.0, 2.0]])
    assert np.isnan(interpolate_on_elements(points, elements, potential, outside)).all()


def test_interpolation_takes_values_on_the_boundary_of_the_mesh():
    points, elements = _square(6)
    value = interpolate_on_elements(
        points, elements, points[:, 0], np.array([[1.0, 0.3], [0.0, 1.0]])
    )
    assert value == pytest.approx([1.0, 0.0], abs=1e-12)


def test_depth_profile_is_at_the_middle_of_a_shifted_mesh():
    lateral = np.linspace(-40e-4, 7640e-4, 5)
    depth = np.linspace(0.0, 300e-4, 4)
    zz, xx = np.meshgrid(depth, lateral, indexing="ij")
    points = np.column_stack([zz.ravel(), xx.ravel()])
    (name, start, end, along), (lateral_name, lstart, lend, lalong) = profile_positions(
        ("z", "x"), points
    )
    assert (name, along) == ("depth", "z")
    assert start[1] == pytest.approx((-40e-4 + 7640e-4) / 2) == end[1]
    assert (start[0], end[0]) == (0.0, 300e-4)
    assert (lateral_name, lalong) == ("lateral", "x")
    assert lstart[0] == pytest.approx(150e-4) == lend[0]
    assert (lstart[1], lend[1]) == (-40e-4, 7640e-4)

    electrode = np.array([[0.0, 3790e-4], [0.0, 3800e-4], [0.0, 3813e-4]])
    _, start, end, _ = profile_positions(("z", "x"), points, electrode)[0]
    assert start[1] == pytest.approx(electrode[:, 1].mean()) == end[1]


def test_cross_section_profiles_run_along_x_and_y_through_the_middle():
    xx, yy = np.meshgrid(
        np.linspace(10.0, 30.0, 5), np.linspace(-4.0, 8.0, 4), indexing="ij"
    )
    points = np.column_stack([xx.ravel(), yy.ravel()])
    (x_name, x_start, x_end, x_along), (y_name, y_start, y_end, y_along) = (
        profile_positions(("x", "y"), points)
    )
    assert (x_name, x_along, y_name, y_along) == ("x", "x", "y", "y")
    assert list(x_start) == [10.0, 2.0] and list(x_end) == [30.0, 2.0]
    assert list(y_start) == [20.0, -4.0] and list(y_end) == [20.0, 8.0]


def test_three_dimensional_depth_profile_is_at_the_middle_of_x_and_y():
    points, _ = _cube(3)
    points = points * [100.0, 40.0, 10.0]
    names = [p[0] for p in profile_positions(("x", "y", "z"), points)]
    assert names == ["depth", "lateral"]
    depth, lateral = profile_positions(("x", "y", "z"), points)
    assert list(depth[1]) == [50.0, 20.0, 0.0] and list(depth[2]) == [50.0, 20.0, 10.0]
    assert list(lateral[1]) == [0.0, 20.0, 5.0] and list(lateral[2]) == [
        100.0,
        20.0,
        5.0,
    ]


def test_a_node_between_a_large_and_a_small_element_leans_to_the_large_one():
    # node 0 is shared by a triangle of area 1/2 where |grad| = 1 and one of
    # area 1/200 where |grad| = 101: the large one weighs 100 times more
    points = np.array([[0.0, 0.0], [1.0, 0.0], [0.0, 1.0], [0.0, -0.01]])
    elements = np.array([[0, 1, 2], [0, 3, 1]])
    potential = np.array([0.0, 1.0, 0.0, -1.0])
    strength = field_strength_at_nodes(points, elements, potential)
    small = np.hypot(1.0, 100.0)
    assert strength[0] == pytest.approx((0.5 * 1.0 + 0.005 * small) / 0.505, rel=1e-12)


def test_a_panel_varying_less_than_one_percent_starts_from_zero():
    assert value_limits(np.array([36.781, 36.785, 36.790])) == pytest.approx(
        (0.0, 1.05 * 36.790)
    )
    assert value_limits(np.array([11.20, 11.34])) is None
    assert value_limits(np.array([-200.0, -200.1])) == pytest.approx(
        (1.05 * -200.1, 0.0)
    )
    assert value_limits(np.zeros(5)) is None


def test_a_profile_title_gives_the_coordinates_fixed_on_the_line():
    assert profile_title(("z", "x"), np.array([0.0, 29e-4]), "z") == "x = 29.0 μm"
    assert profile_title(("z", "x"), np.array([25e-4, 0.0]), "x") == "Depth = 25.0 μm"
    assert (
        profile_title(("x", "y", "z"), np.array([50e-4, 20e-4, 0.0]), "z")
        == "x = 50.0, y = 20.0 μm"
    )


def _implanted_cell():
    """Nodes (depth, x) [cm] of one cell 80 um wide and 50 um deep, with an
    implant 1 um deep under 30 < x < 50 um on a bulk of 1e12."""
    zz, xx = np.meshgrid(
        np.linspace(0, 50e-4, 101), np.linspace(0, 80e-4, 33), indexing="ij"
    )
    points = np.column_stack([zz.ravel(), xx.ravel()])
    under = (points[:, 0] < 1e-4) & (points[:, 1] > 30e-4) & (points[:, 1] < 50e-4)
    return points, np.where(under, 1e19, 1e12)


def test_a_boundary_is_found_where_the_doping_steps_along_the_depth():
    points, doping = _implanted_cell()
    start, end = np.array([0.0, 40e-4]), np.array([50e-4, 40e-4])
    (depth,) = boundaries_on_line(points, doping, ("z", "x"), start, end, "z")
    assert depth == pytest.approx(1.0, abs=0.5)
    start, end = np.array([0.0, 10e-4]), np.array([50e-4, 10e-4])
    assert boundaries_on_line(points, doping, ("z", "x"), start, end, "z") == []


def test_a_line_in_a_row_of_cells_takes_the_doping_of_its_place_in_the_cell():
    # 47 cells further along x the line is again under the implant of a cell
    points, doping = _implanted_cell()
    start, end = (
        np.array([0.0, 40e-4 + 47 * 80e-4]),
        np.array([50e-4, 40e-4 + 47 * 80e-4]),
    )
    (depth,) = boundaries_on_line(points, doping, ("z", "x"), start, end, "z")
    assert depth == pytest.approx(1.0, abs=0.5)
