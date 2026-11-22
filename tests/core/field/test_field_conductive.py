import numpy as np
import pytest

from raser.core.field.conductive import ELEMENTARY_CHARGE
from raser.core.field.conductive import conductive
from raser.core.field.conductive import undepleted_bulk
from raser.core.field.conductive import undepleted_layer_of_mesh

MU_N, MU_P = 1400.0, 450.0  # cm^2/(V s), silicon


def _is_conductive(electrons, holes, net_doping):
    return bool(conductive([electrons], [holes], [net_doping], MU_N, MU_P)[0])


def test_a_heavily_doped_substrate_is_conductive() -> None:
    # p-type 1e18 cm^-3 with all its holes: 0.014 Ohm cm
    assert _is_conductive(electrons=1e2, holes=1e18, net_doping=-1e18)


def test_a_depleted_bulk_is_dielectric() -> None:
    assert not _is_conductive(electrons=28.0, holes=77.0, net_doping=-5e12)


def test_a_high_resistivity_bulk_that_is_not_depleted_is_conductive() -> None:
    # p-type 5e12 cm^-3 with all its holes: 2.8 kOhm cm, far above 10 Ohm cm
    assert _is_conductive(electrons=1.7e7, holes=5e12, net_doping=-5e12)


def test_without_net_doping_only_the_resistivity_decides() -> None:
    assert not _is_conductive(
        electrons=1e10, holes=1e10, net_doping=0.0
    )  # intrinsic silicon
    assert not _is_conductive(
        electrons=1e-20, holes=1e-20, net_doping=0.0
    )  # an insulator
    assert _is_conductive(electrons=1e18, holes=1e2, net_doping=0.0)


def _planar(depleted_to_um):
    """A 100 um p-type bulk of 1e12 cm^-3 between an n+ and a p+ layer of
    1 um, depleted from the n+ layer down to `depleted_to_um`. Nodes are 1 um
    apart, and given out of order."""
    depth_um = np.arange(0.0, 101.0)
    net_doping = np.full(101, -1.0e12)
    net_doping[0], net_doping[100] = 1.0e19, -1.0e19
    electrons = np.where(depth_um < 1, 1.0e19, 1.0e2)
    holes = np.where(depth_um > 99, 1.0e19, np.where(depth_um >= depleted_to_um, 1.0e12, 1.0e2))
    order = np.random.default_rng(3).permutation(101)
    return depth_um[order] * 1e-4, electrons[order], holes[order], net_doping[order]


def test_the_undepleted_bulk_is_what_lies_between_the_depletion_and_the_contact_layer() -> None:
    width, resistance = undepleted_bulk(*_planar(depleted_to_um=60), MU_N, MU_P)
    # the nodes from 60 to 99 um carry the holes of the bulk: 39 um of 13.9 kOhm cm
    resistivity = 1.0 / (ELEMENTARY_CHARGE * (MU_P * 1.0e12 + MU_N * 1.0e2))
    assert width == pytest.approx(39.0e-4)
    assert resistance == pytest.approx(resistivity * 39.0e-4)


def test_a_fully_depleted_device_has_no_undepleted_bulk() -> None:
    assert undepleted_bulk(*_planar(depleted_to_um=100), MU_N, MU_P) == (0.0, 0.0)


def test_the_undepleted_layer_of_a_mesh_is_that_of_its_columns_along_the_depth() -> None:
    # 5 columns 2 um wide, each 11 nodes 1 um apart along the depth with the
    # same profile: depleted down to 3 um, undepleted from 4 um to 10 um,
    # n-type 1e12 cm^-3 with all its electrons there: 4.6 kOhm cm.
    step_cm, column_cm, columns = 1e-4, 2e-4, 5
    depth = np.arange(11) * step_cm
    net_doping = np.full(11, 1.0e12)
    electrons = np.where(np.arange(11) >= 4, 1.0e12, 0.0)
    holes = np.zeros(11)
    mu_n, mu_p = 1350.0, 480.0
    # Volume of a node along the depth: its own cell, half a step on either
    # side, half a step at the two ends of the column. The sum along the
    # depth adds the intervals whose two nodes are both undepleted, 4 to 10
    # um; the sum over nodes adds the cells of the undepleted nodes, which
    # reach half a step beyond the first of them, 3.5 to 10 um. The first
    # undepleted node is given only the half of its cell towards the bulk,
    # as if it were an end: both sums then cover 4 to 10 um, with one
    # resistivity, and are the same.
    cell = np.full(11, step_cm)
    cell[[0, 10]] = step_cm / 2
    cell[4] = step_cm / 2
    volumes = np.tile(cell * column_cm, columns)

    width, resistance = undepleted_layer_of_mesh(
        volumes,
        columns * column_cm,
        np.tile(electrons, columns),
        np.tile(holes, columns),
        np.tile(net_doping, columns),
        mu_n,
        mu_p,
    )

    along_depth = undepleted_bulk(depth, electrons, holes, net_doping, mu_n, mu_p)
    assert along_depth[0] == pytest.approx(6e-4, rel=1e-12, abs=0)
    assert width == pytest.approx(along_depth[0], rel=1e-12, abs=0)
    assert resistance == pytest.approx(along_depth[1], rel=1e-12, abs=0)
