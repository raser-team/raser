"""Time-resolution experiment application."""

import json
from pathlib import Path

from raser.stages import chain
from raser.lifecycle.workflow import Workflow

DEFAULTS = json.loads((Path(__file__).parent / "time_resolution.json").read_text("utf-8"))

# The two slots of the time_resolution setup: the reference, the device of the
# command under test.
DEVICES = {"ref": ("HPK-Si-LGAD", ["ref"]), "dut": (None, ["dut"])}

WORKFLOW = Workflow(
    name="timeres",
    keys=chain.keys_of(DEVICES),
    defaults={
        **chain.DEFAULTS,
        **{f"deposit.{key}": value for key, value in DEFAULTS.items()},
        "deposit.events_per_job": 10000,
        "deposit.plots": 0,
        "current.plots": 0,
    },
    sections=chain.SECTIONS,
    scanned=chain.SCANNED,
    slots=chain.SLOTS,
    components=chain.COMPONENTS,
    readers=chain.READERS,
    in_file=chain.in_file_of(DEVICES),
    slices=chain.expand(DEVICES),
    devices=DEVICES,
    exclusive=chain.EXCLUSIVE,
    command=chain.job_command,
    analysis=chain.analyse,
)


def register(subparsers):
    parser = subparsers.add_parser("timeres", help="time-resolution experiment")
    chain.add_arguments(parser)
    WORKFLOW.attach(parser)
    parser.set_defaults(_project="det_name", _components=("raser_bench/timeres", "raser_bench/signal"))
