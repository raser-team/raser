"""Time-resolution experiment application."""

import json
from pathlib import Path

from raser.stages import chain
from raser.lifecycle.workflow import Workflow

DEFAULTS = json.loads((Path(__file__).parent / "time_resolution.json").read_text("utf-8"))


WORKFLOW = Workflow(
    name="timeres",
    keys=chain.KEYS,
    defaults={**chain.DEFAULTS, **DEFAULTS, "events_per_job": 10000, "plots": 0},
    components=chain.COMPONENTS,
    readers=chain.READERS,
    in_file=chain.IN_FILE,
    slices=chain.SLICES,
    exclusive=chain.EXCLUSIVE,
    command=chain.job_command,
    analysis=chain.analyse,
)


def register(subparsers):
    parser = subparsers.add_parser("timeres", help="time-resolution experiment")
    chain.add_arguments(parser)
    WORKFLOW.attach(parser)
    parser.set_defaults(_project="det_name", _components=("raser_bench/timeres", "raser_bench/signal"))
