from __future__ import annotations

import csv
from array import array
from pathlib import Path

import pytest


pytestmark = pytest.mark.root


def test_root_tree_conversion_preserves_branch_values(tmp_path: Path) -> None:
    import ROOT

    from raser.supports.root_tree import root_tree_to_csv

    root_path = tmp_path / "events.root"
    root_file = ROOT.TFile(str(root_path), "RECREATE")
    tree = ROOT.TTree("events", "events")
    energy = array("d", [0.0])
    tree.Branch("energy", energy, "energy/D")
    for value in (1.5, 2.5):
        energy[0] = value
        tree.Fill()
    tree.Write()
    root_file.Close()

    csv_path = root_tree_to_csv(tmp_path / "events.csv", root_path, "events")
    with csv_path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.reader(stream))

    assert rows == [["energy"], ["1.5"], ["2.5"]]
