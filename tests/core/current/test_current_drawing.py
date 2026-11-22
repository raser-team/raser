"""Which electrodes the current pictures are drawn for."""

import re
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from raser.core.current.cal_current import write_induced_currents
from raser.core.current.draw import draw_currents
from raser.core.deposit.deposits import Deposits, EventDeposits, write_deposits

sys.path.insert(0, str(Path(__file__).parent))
from test_current_gain_time_axis import _lgad, _NoFieldBelow10um, _UniformField  # noqa: E402


def test_only_the_electrodes_with_current_are_drawn_those_whose_parts_cancel_included(tmp_path) -> None:
    # electrode 1 has no current; on electrode 2 the holes and the electrons
    # cancel, as on a strip beside the one hit; electrode 3 has current
    holes = np.zeros((4, 10))
    electrons = np.zeros((4, 10))
    holes[1, 2:5], electrons[1, 2:5] = 1e-6, -1e-6
    holes[2, 2:5], electrons[2, 2:5] = 1e-6, 2e-6
    # electrode 4: a bipolar hole current whose integral is zero
    holes[3, 2:4], holes[3, 4:6] = 1e-6, -1e-6

    draw_currents(str(tmp_path), 4, 0.0, 5e-12, holes + electrons, holes, electrons)

    assert sorted(path.name for path in tmp_path.glob("*.pdf")) == [
        "current_4_electrode_2.pdf",
        "current_4_electrode_3.pdf",
        "current_4_electrode_4.pdf",
    ]


def test_the_pictures_drawn_again_are_those_of_this_run_only(tmp_path) -> None:
    # a picture an earlier run left for an electrode this run does not hit goes
    deposits = tmp_path / "deposit.h5"
    write_deposits(
        str(deposits),
        Deposits(1, {}, "any", None, [EventDeposits(4, ["d"], [50.0], [50.0], [25.0], [0.0], [0.01], pairs=[100.0])]),
    )
    stale = tmp_path / "plots" / "current_4_electrode_7.pdf"
    stale.parent.mkdir(parents=True)
    stale.write_text("from an earlier run")
    device = SimpleNamespace(**{**vars(_lgad()), "has_avalanche": False, "is_strip": False, "is_pixel": False})

    write_induced_currents(str(deposits), str(tmp_path / "current.h5"), device, _UniformField(), 1, str(tmp_path / "plots"))

    assert not stale.exists()
    assert (stale.parent / "current_4.pdf").exists()



def test_a_job_warns_of_the_carriers_that_found_no_field_with_where(tmp_path, caplog) -> None:
    deposits = tmp_path / "deposit.h5"
    write_deposits(
        str(deposits),
        Deposits(1, {}, "any", None, [EventDeposits(4, ["d"], [50.0], [50.0], [25.0], [0.0], [0.01], pairs=[100.0])]),
    )
    device = SimpleNamespace(**{**vars(_lgad()), "has_avalanche": False, "is_strip": False, "is_pixel": False})

    write_induced_currents(str(deposits), str(tmp_path / "current.h5"), device, _NoFieldBelow10um(), 0, None)

    warnings = [record.getMessage() for record in caplog.records if record.levelname == "WARNING"]
    assert len(warnings) == 1
    # the electrons diffuse a little on their way down to 10 um
    assert re.search(r"^1 clusters \(100 carriers\) .* event 4 at x, y, z = [\d.]+, [\d.]+, 9\.\d+ um", warnings[0])
