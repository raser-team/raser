"""
Description:  signal/__init__.py
@Date       : 2025
@Author     : Xin Shi, Chenxi Fu, Jian Feng
@version    : 2.0
"""

import json
from pathlib import Path

from raser.lifecycle.workflow import Workflow

DEFAULTS = json.loads((Path(__file__).parent / "signal.json").read_text("utf-8"))
KEYS = ("source", "events_per_job", "plots", "voltage", "irradiation", "amplifier", "adc")
COMPONENTS = {"source": "source", "afe": "amplifier"}  # kind of file -> option
IN_FILE = {"voltage": "device.bias.voltage"}  # option -> where it sits in a file


def add_arguments(parser):
    parser.add_argument("det_name", help="Device project")
    parser.add_argument(
        "source",
        nargs="?",
        help="signal source or beam configuration",
    )
    parser.add_argument("-evt", "--events-per-job", type=int, help="events per job")
    parser.add_argument("--plots", type=int, help="draw the first N recorded events of each job")
    parser.add_argument("-vol", "--voltage", type=float, help="bias voltage")
    parser.add_argument("-irr", "--irradiation", type=float, help="irradiation flux")
    parser.add_argument(
        "-g4_vis", help="visualization of Geant4 experiment", action="store_true"
    )
    parser.add_argument("--g4-vis-driver", help="Geant4 visualization driver")
    parser.add_argument("-amp", "--amplifier", type=str, help="amplifier")
    parser.add_argument("--adc", help="ADC component")


def job_command(kwargs):
    command = []
    if kwargs.get("g4_vis"):
        command.append("-g4_vis")
    if kwargs.get("g4_vis_driver"):
        command.extend(["--g4-vis-driver", kwargs["g4_vis_driver"]])
    return command


def run_job(kwargs):
    """One signal job inside its seed folder."""
    from . import gen_signal

    gen_signal.main(kwargs)


WORKFLOW = Workflow(
    name="signal",
    keys=KEYS,
    defaults={
        "source": DEFAULTS["source"],
        "amplifier": DEFAULTS["afe"],
        "events_per_job": 1,
        "plots": 100,
    },
    components=COMPONENTS,
    in_file=IN_FILE,
    job=run_job,
    command=job_command,
)


def register(subparsers):
    parser = subparsers.add_parser("signal", help="single signal simulation")
    add_arguments(parser)
    WORKFLOW.attach(parser)
    parser.set_defaults(_project="det_name", _components=("signal",))
