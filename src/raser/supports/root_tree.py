"""
Description:  root_tree.py
@Date       : 2023
@Author     : Ye He
@version    : 1.0
"""

import csv
from pathlib import Path

import ROOT


def root_tree_to_csv(csv_file_name, root_file_name, tree_name):
    root_file = ROOT.TFile(str(root_file_name), "READ")
    try:
        tree = root_file.Get(tree_name)
        if tree is None:
            raise KeyError(f"ROOT tree is missing: {tree_name}")
        branches = tuple(tree.GetListOfBranches())
        destination = Path(csv_file_name)
        with destination.open(mode="w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow([branch.GetName() for branch in branches])
            for event in tree:
                writer.writerow(
                    [event.GetLeaf(branch.GetName()).GetValue() for branch in branches]
                )
        return destination
    finally:
        root_file.Close()
