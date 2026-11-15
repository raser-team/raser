"""Time-resolution experiment application."""

import json
from pathlib import Path

from raser.apps import signal
from raser.lifecycle.workflow import Workflow

DEFAULTS = json.loads((Path(__file__).parent / "time_resolution.json").read_text("utf-8"))


WORKFLOW = Workflow(
    name="timeres",
    keys=signal.KEYS + ("g4setup",),
    defaults={
        "source": DEFAULTS["source"],
        "events_per_job": 10000,
        "plots": 0,
        "amplifier": DEFAULTS["afe"],
        "g4setup": DEFAULTS["g4setup"],
    },
    components={**signal.COMPONENTS, "g4setup": "g4setup"},
    in_file=signal.IN_FILE,
    slices=signal.SLICES,
    command=signal.job_command,
)


def register(subparsers):
    parser = subparsers.add_parser("timeres", help="time-resolution experiment")
    signal.add_arguments(parser)
    WORKFLOW.attach(parser)
    parser.set_defaults(_project="det_name", _components=("timeres", "signal"))
