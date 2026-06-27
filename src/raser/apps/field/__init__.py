"""Field asset application."""

import logging
import os
import subprocess

from raser.core.field import extract_from_tcad
from raser.core.field import solver_section
from raser.core.field import weighting_potential


def _configure_logging(verbose):
    if verbose == 1:
        logging.basicConfig(level=logging.INFO)
    if verbose == 2:
        logging.basicConfig(level=logging.DEBUG)


def _run_umf(kwargs):
    dirname = os.path.dirname(os.path.abspath(solver_section.__file__))
    solver_path = os.path.abspath(os.path.join(dirname, "solver_section.py"))
    command = "python3 -mdevsim.umfpack.umfshim " + solver_path + " " + repr(str(kwargs))
    subprocess.run([command], shell=True)


def solve(kwargs):
    _configure_logging(kwargs["verbose"])
    if kwargs["umf"] is True:
        _run_umf(kwargs)
    else:
        solver_section.main(kwargs)


def import_field(kwargs):
    _configure_logging(kwargs["verbose"])
    extract_from_tcad.main(kwargs["target"], is_flip=kwargs["flip"])


def weight(voltage, electrode, target):
    weighting_potential.main(voltage, electrode, target)


def main(kwargs):
    if kwargs["extract"] is True:
        import_field(kwargs)
    elif kwargs["wf_sub"] is not None:
        weight(kwargs["wf_sub"][0], kwargs["wf_sub"][1], kwargs["target"])
    else:
        solve(kwargs)
