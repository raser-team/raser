"""Time-resolution experiment application."""

import json
from pathlib import Path

from raser.apps import signal
from raser.lifecycle.workflow import Workflow

DEFAULTS = json.loads((Path(__file__).parent / "time_resolution.json").read_text("utf-8"))


def _job(kwargs):
    from .g4_interaction import TimeresActionInitialization

    kwargs["_g4_action_initialization"] = TimeresActionInitialization
    signal.run_job(kwargs, "timeres")


def _extract(point_root, done):
    from raser.apps.timeres import summary

    return summary.collect_point(point_root, done)


WORKFLOW = Workflow(
    name="timeres",
    keys=signal.KEYS + ("g4setup",),
    defaults={
        "source": DEFAULTS["source"],
        "events_per_job": 10000,
        "amplifier": DEFAULTS["afe"],
        "adc": DEFAULTS["adc"],
        "g4setup": DEFAULTS["g4setup"],
    },
    components={**signal.COMPONENTS, "g4setup": "g4setup", "adc": "adc"},
    in_file=signal.IN_FILE,
    job=_job,
    extract=_extract,
    command=signal.job_command,
)


def register(subparsers):
    parser = subparsers.add_parser("timeres", help="time-resolution experiment")
    signal.add_arguments(parser)
    WORKFLOW.attach(parser)
    parser.set_defaults(_project="det_name", _components=("timeres", "signal"))
