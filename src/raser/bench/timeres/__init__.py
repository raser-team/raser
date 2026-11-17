"""Time-resolution experiment application."""

import json
from pathlib import Path

from raser.stages import chain
from raser.lifecycle.workflow import Workflow

DEFAULTS = json.loads((Path(__file__).parent / "time_resolution.json").read_text("utf-8"))


WORKFLOW = Workflow(
    name="timeres",
    keys=chain.KEYS,
    defaults={
        "source": DEFAULTS["source"],
        "fano": True,
        "events_per_job": 10000,
        "plots": 0,
        "amplifier": DEFAULTS["afe"],
        "g4setup": DEFAULTS["g4setup"],
    },
    components=chain.COMPONENTS,
    in_file=chain.IN_FILE,
    slices=chain.SLICES,
    command=chain.job_command,
)


def register(subparsers):
    parser = subparsers.add_parser("timeres", help="time-resolution experiment")
    chain.add_arguments(parser)
    WORKFLOW.attach(parser)
    parser.set_defaults(_project="det_name", _components=("bench/timeres", "bench/signal"))
