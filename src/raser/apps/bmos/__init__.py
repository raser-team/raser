"""Beam monitor: the pulses that the bunches of a beam leave in one detector.

An event is one bunch: a source whose "particles" are fired together in
every event. The slices are those of the signal app; the default source is
the bunch in components/source of this app.
"""

from raser.apps import signal
from raser.lifecycle.workflow import Workflow

WORKFLOW = Workflow(
    name="bmos",
    keys=signal.KEYS,
    defaults={**signal.WORKFLOW.defaults, "source": "bunch", "plots": 0},
    components=signal.COMPONENTS,
    in_file=signal.IN_FILE,
    slices=signal.SLICES,
    command=signal.job_command,
)


def register(subparsers):
    parser = subparsers.add_parser("bmos", help="Beam Monitor Online System")
    signal.add_arguments(parser)
    WORKFLOW.attach(parser)
    parser.set_defaults(_project="det_name", _components=("bmos",))
