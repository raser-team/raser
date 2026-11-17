"""
Description:  signal/__init__.py
@Date       : 2025
@Author     : Xin Shi, Chenxi Fu, Jian Feng
@version    : 2.0
"""

import json
from pathlib import Path

from raser.lifecycle.workflow import Workflow
from raser.stages import chain

DEFAULTS = json.loads((Path(__file__).parent / "signal.json").read_text("utf-8"))


WORKFLOW = Workflow(
    name="signal",
    keys=chain.KEYS,
    defaults={
        "source": DEFAULTS["source"],
        "g4setup": "device_alone",
        "fano": True,
        "amplifier": DEFAULTS["afe"],
        "events_per_job": 1,
        "plots": 100,
    },
    components=chain.COMPONENTS,
    in_file=chain.IN_FILE,
    slices=chain.SLICES,
    command=chain.job_command,
)


def register(subparsers):
    parser = subparsers.add_parser("signal", help="single signal simulation")
    chain.add_arguments(parser)
    WORKFLOW.attach(parser)
    parser.set_defaults(_project="det_name", _components=("signal",))
