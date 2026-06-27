"""Reusable field calculation entry points."""

from . import solver_section
from . import weighting_potential


def main(kwargs):
    solver_section.main(kwargs)


def derive_weight(voltage, electrode, target):
    weighting_potential.main(voltage, electrode, target)
