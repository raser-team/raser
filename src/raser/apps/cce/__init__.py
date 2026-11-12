"""Charge-collection experiment application."""

import json
from pathlib import Path

from raser.apps import signal
from raser.lifecycle.workflow import Workflow

DEFAULTS = json.loads((Path(__file__).parent / "charge_collection.json").read_text("utf-8"))


def _job(kwargs):
    signal.run_job(kwargs, "cce")


def _extract(point_root, done):
    from raser.apps.cce import summary

    return summary.collect_point(point_root, done)


WORKFLOW = Workflow(
    name="cce",
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
    parser = subparsers.add_parser("cce", help="charge-collection experiment")
    signal.add_arguments(parser)
    WORKFLOW.attach(parser)
    parser.set_defaults(_project="det_name", _components=("cce", "signal"))
