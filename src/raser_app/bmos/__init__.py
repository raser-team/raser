"""Beam monitor: the pulses that the bunches of a beam leave in one detector.

An event is one bunch: a source whose "particles" are fired together in
every event. The slices are those of the signal app; the default source is
the bunch in components/source of this app.
"""

from raser.stages import chain
from raser.lifecycle.workflow import Workflow

WORKFLOW = Workflow(
    name="bmos",
    keys=chain.KEYS,
    defaults={**chain.DEFAULTS, "source": "bunch", "plots": 0},
    components=chain.COMPONENTS,
    readers=chain.READERS,
    in_file=chain.IN_FILE,
    slices=chain.SLICES,
    exclusive=chain.EXCLUSIVE,
    command=chain.job_command,
)


def register(subparsers):
    parser = subparsers.add_parser("bmos", help="Beam Monitor Online System")
    chain.add_arguments(parser)
    WORKFLOW.attach(parser)
    parser.set_defaults(_project="det_name", _components=("raser_app/bmos",))
