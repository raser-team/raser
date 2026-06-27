from types import SimpleNamespace

import pytest
import ROOT

from raser.core.current.cal_current import CalCurrent
from raser.core.current.cal_current import t_tol


@pytest.mark.root
def test_system_current_histogram_matches_root_fill_for_fixed_signal_input():
    current = object.__new__(CalCurrent)
    current.read_ele_num = 1
    current.t_bin = 5.0e-12
    current.delta_t = 2.0e-12

    hist_id = id(current)
    current.positive_cu = [
        ROOT.TH1F(f"fixed_signal_positive_{hist_id}", "", 8, -2.0e-12, 14.0e-12)
    ]
    current.negative_cu = [
        ROOT.TH1F(f"fixed_signal_negative_{hist_id}", "", 8, -2.0e-12, 14.0e-12)
    ]
    fixed_signals = [1.0e-18, 2.0e-18, -1.0e-18]
    fixed_path = [
        [0.0, 0.0, 0.0, 0, 0, 0],
        [0.0, 0.0, 1.0, 1, 0, 0],
        [0.0, 0.0, 2.0, 2, 0, 0],
        [0.0, 0.0, 3.0, 3, 0, 0],
    ]
    carrier_system = SimpleNamespace(
        positions=[[0.0, 0.0, 0.0]],
        signals=[[fixed_signals]],
        paths_reduced=[fixed_path],
    )

    signals_found = current._process_system_current(
        carrier_system, 1, 1, 0, 0, 1, "hole"
    )

    expected = ROOT.TH1F(f"fixed_signal_expected_{hist_id}", "", 8, -2.0e-12, 14.0e-12)
    for step_idx, signal in enumerate(fixed_signals):
        expected.Fill(
            fixed_path[step_idx][3] * current.delta_t + t_tol,
            signal / current.t_bin,
        )

    assert signals_found == len(fixed_signals)
    for bin_idx in range(expected.GetNbinsX() + 2):
        assert current.positive_cu[0].GetBinContent(bin_idx) == pytest.approx(
            expected.GetBinContent(bin_idx)
        )
