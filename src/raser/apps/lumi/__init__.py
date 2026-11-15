"""CEPC fast luminosity monitor: what the lost electrons of a bunch leave in
the pads beside the beam pipe.

An event is one bunch. Only the deposits are written so far: the currents
and the waveforms of the signal app follow once the current of one detector
of a deposits file can be asked for.
"""

from raser.lifecycle.slices import Slice
from raser.lifecycle.workflow import Workflow


def _deposits(kwargs):
    from . import deposits

    deposits.deposits(kwargs)


SLICES = (Slice("deposits", _deposits),)

WORKFLOW = Workflow(name="lumi", slices=SLICES)


def register(subparsers):
    parser = subparsers.add_parser("lumi", help="CEPC Fast Luminosity Monitor")
    parser.add_argument("det_name", help="Device project")
    WORKFLOW.attach(parser)
    parser.set_defaults(_project="det_name")
