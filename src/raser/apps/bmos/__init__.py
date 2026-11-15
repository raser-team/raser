"""Beam monitor: the pulses that the bunches of a beam leave in one detector.

An event is one bunch. Its slices are those of the signal app; only the
deposits are its own, until the Geant4 entry of core/interaction shoots
several particles in one event.
"""

from raser.apps import signal
from raser.lifecycle.slices import Slice
from raser.lifecycle.workflow import Workflow


def _deposits(kwargs):
    from . import deposits

    deposits.deposits(kwargs)


SLICES = (Slice("deposits", _deposits), *signal.SLICES[1:])

WORKFLOW = Workflow(
    name="bmos",
    keys=("voltage", "irradiation", "plots", "amplifier"),
    defaults={"amplifier": signal.DEFAULTS["afe"], "plots": 0},
    in_file=signal.IN_FILE,
    slices=SLICES,
)


def register(subparsers):
    parser = subparsers.add_parser("bmos", help="Beam Monitor Online System")
    parser.add_argument("det_name", help="Device project")
    parser.add_argument("--plots", type=int, help="draw the first N recorded bunches of each job")
    parser.add_argument("-vol", "--voltage", type=float, help="bias voltage")
    parser.add_argument("-irr", "--irradiation", type=float, help="irradiation flux")
    parser.add_argument("-amp", "--amplifier", type=str, help="amplifier")
    WORKFLOW.attach(parser)
    parser.set_defaults(_project="det_name")
