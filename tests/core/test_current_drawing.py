"""Which electrodes the current pictures are drawn for."""

import numpy as np

from raser.core.current.draw import draw_currents


def test_only_the_electrodes_with_current_are_drawn_those_whose_parts_cancel_included(tmp_path) -> None:
    # electrode 1 has no current; on electrode 2 the holes and the electrons
    # cancel, as on a strip beside the one hit; electrode 3 has current
    holes = np.zeros((3, 10))
    electrons = np.zeros((3, 10))
    holes[1, 2:5], electrons[1, 2:5] = 1e-6, -1e-6
    holes[2, 2:5], electrons[2, 2:5] = 1e-6, 2e-6

    draw_currents(str(tmp_path), 0.0, 5e-12, holes + electrons, holes, electrons)

    assert sorted(path.name for path in tmp_path.glob("*.pdf")) == [
        "No_2electrode_basic_infor.pdf",
        "No_3electrode_basic_infor.pdf",
    ]
