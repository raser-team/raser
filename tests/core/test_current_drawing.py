"""Which electrodes the current pictures are drawn for."""

import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from raser.core.current.cal_current import write_induced_currents
from raser.core.current.draw import draw_currents
from raser.core.deposit.deposits import Deposits, EventDeposits, write_deposits

sys.path.insert(0, str(Path(__file__).parent))
from test_current_gain_time_axis import _lgad, _UniformField  # noqa: E402


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


def test_the_pictures_of_an_event_drawn_again_are_those_of_this_run_only(tmp_path) -> None:
    # a picture an earlier run left for a strip this run does not hit goes
    deposits = tmp_path / "deposit.h5"
    write_deposits(
        str(deposits),
        Deposits(1, None, None, [EventDeposits(4, ["d"], [50.0], [50.0], [25.0], [0.0], [0.01], pairs=[100.0])]),
    )
    stale = tmp_path / "plots" / "event_4" / "No_7electrode_basic_infor.pdf"
    stale.parent.mkdir(parents=True)
    stale.write_text("from an earlier run")
    device = SimpleNamespace(**{**vars(_lgad()), "has_avalanche": False, "is_strip": False, "is_pixel": False})

    write_induced_currents(str(deposits), str(tmp_path / "current.h5"), device, _UniformField(), 1, str(tmp_path / "plots"))

    assert not stale.exists()
    assert (stale.parent / "No_1electrode_basic_infor.pdf").exists()
