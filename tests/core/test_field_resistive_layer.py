import numpy as np
import pytest

from raser.core.field.resistive_layer import resistive_grid
from raser.core.field.resistive_layer import resistive_row
from raser.core.readout.spice import solve

pytestmark = pytest.mark.ngspice

# every read-out on 50 Ohm, through a wire
WIRE = {
    "ports": {"in": "a", "out": "b"},
    "elements": {"R1": {"between": ["a", "b"], "ohm": 1e-6}},
}
LOAD = {
    "ports": {"in": "a"},
    "elements": {"R1": {"between": ["a", "0"], "ohm": 50.0}},
}
ON_THE_LOAD = {"stages": {"wire": WIRE}, "load": LOAD}
DT_S = 20e-12
BINS = 1000
# 1 fC in the first ten bins
PULSE = np.where(np.arange(BINS) < 10, 1e-15 / (10 * DT_S), 0.0)
# a layer of 1 kOhm a square with 1 uF / m^2 under it: cells of 10 x 1000 um
# have 10 fF each and 10 Ohm from one middle to the next
CELL_M, LENGTH_M = 10e-6, 1e-3
SHEET_OHM, PER_AREA_F_M2 = 1000.0, 1e-6


def _layer_ohm(um):
    """Resistance of the layer across um of it, along the length of the row."""
    return SHEET_OHM * um * 1e-6 / LENGTH_M


def _charges(sensor, cell):
    """Charge [fC] that 1 fC on a cell sends through the load of each read-out."""
    cells = list(sensor.sources)
    currents = np.zeros((len(cells), BINS))
    currents[cells.index(cell)] = PULSE
    voltage = solve(ON_THE_LOAD, cells, DT_S, currents, sensor)
    return voltage.sum(axis=1) * DT_S / 50.0 * 1e15


def test_charge_between_two_strips_is_shared_by_the_distances_to_them():
    # strips on the cells 2 to 4 and 15 to 17; cells beyond them end open
    cells = [f"c{k}" for k in range(20)]
    sensor = resistive_row(
        cells,
        CELL_M,
        LENGTH_M,
        SHEET_OHM,
        PER_AREA_F_M2,
        {"left": (2, 4), "right": (15, 17)},
    )
    # the layer between the strips runs from the edge of the cell 4 to that
    # of the cell 15, from 50 to 150 um. All the charge leaves through the
    # loads, shared as a steady current would be
    for cell in (5, 8, 12, 14):
        to_left, to_right = _charges(sensor, f"c{cell}")
        centre_um = (cell + 0.5) * 10
        left_ohm = _layer_ohm(centre_um - 50) + 50.0
        right_ohm = _layer_ohm(150 - centre_um) + 50.0
        share = right_ohm / (left_ohm + right_ohm)
        assert to_left == pytest.approx(share, rel=0.01)
        assert to_right == pytest.approx(1 - share, rel=0.01)
    assert sum(_charges(sensor, "c0")) == pytest.approx(1, rel=0.01)
    # a cell beyond a strip feeds the strip, which passes some of it on
    to_left, to_right = _charges(sensor, "c18")
    beyond = 50.0 / (50.0 + _layer_ohm(100) + 50.0)
    assert to_left == pytest.approx(beyond, rel=0.01)


def test_charge_beside_a_grounded_contact_is_partly_lost_to_it():
    cells = [f"c{k}" for k in range(12)]
    sensor = resistive_row(
        cells,
        CELL_M,
        LENGTH_M,
        SHEET_OHM,
        PER_AREA_F_M2,
        {"strip": (0, 1)},
        {"ring": (10, 11)},
    )
    # from the middle of the cell 5: 35 um of layer to the strip, on its
    # load, and 45 um to the ring
    (to_strip,) = _charges(sensor, "c5")
    to_strip_ohm = _layer_ohm(35) + 50.0
    assert to_strip == pytest.approx(
        _layer_ohm(45) / (_layer_ohm(45) + to_strip_ohm), rel=0.01
    )


@pytest.mark.parametrize("along", ["x", "y"])
def test_grid_one_cell_wide_is_a_row(along):
    count = 12
    cells = [f"c{k}" for k in range(count)]
    strips = {"left": (1, 2), "right": (8, 9)}
    row = resistive_row(cells, CELL_M, LENGTH_M, SHEET_OHM, PER_AREA_F_M2, strips)
    if along == "x":
        counts, widths = (count, 1), (CELL_M, LENGTH_M)
        pads = {name: (first, last, 0, 0) for name, (first, last) in strips.items()}
    else:
        counts, widths = (1, count), (LENGTH_M, CELL_M)
        pads = {name: (0, 0, first, last) for name, (first, last) in strips.items()}
    grid = resistive_grid(cells, counts, widths, SHEET_OHM, PER_AREA_F_M2, pads)

    currents = np.zeros((count, BINS))
    currents[4] = PULSE
    np.testing.assert_allclose(
        solve(ON_THE_LOAD, cells, DT_S, currents, grid),
        solve(ON_THE_LOAD, cells, DT_S, currents, row),
        rtol=1e-6,
        atol=1e-12,
    )


def test_pads_coupled_to_a_grounded_layer_carry_no_net_charge():
    # 5 x 5 cells of 100 um under 1 kOhm a square, 70 um of SiC below, a pad
    # over the cell (1, 1) and one over (3, 3) on 0.5 um of oxide, the layer
    # held on ground at a corner. The charge leaves through the ground, in
    # some ns; the pads see it pass
    cells = [f"c{k}" for k in range(25)]
    sensor = resistive_grid(
        cells,
        (5, 5),
        (100e-6, 100e-6),
        1e3,
        9.7 * 8.854e-12 / 70e-6,
        {"near": (1, 1, 1, 1), "far": (3, 3, 3, 3)},
        coupling_per_area_f_m2=3.9 * 8.854e-12 / 0.5e-6,
        grounded={"corner": [(0, 0, 0, 0)]},
    )
    dt = 100e-12
    currents = np.zeros((25, BINS))
    currents[1 * 5 + 2, 0] = 1e-15 / dt  # beside the near pad
    voltage = solve(ON_THE_LOAD, cells, dt, currents, sensor)

    near, far = voltage
    assert np.abs(near).max() > 2 * np.abs(far).max()
    for pad in (near, far):
        assert abs(pad.sum()) < 0.02 * np.abs(pad).sum()
