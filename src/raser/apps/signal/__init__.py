"""
Description:  signal/__init__.py
@Date       : 2025
@Author     : Xin Shi, Chenxi Fu, Jian Feng
@version    : 2.0
"""

import json
from pathlib import Path

from raser.lifecycle.slices import Slice
from raser.lifecycle.workflow import Workflow

DEFAULTS = json.loads((Path(__file__).parent / "signal.json").read_text("utf-8"))
KEYS = (
    "source",
    "events_per_job",
    "edep_min",
    "edep_max",
    "plots",
    "voltage",
    "irradiation",
    "amplifier",
)
COMPONENTS = {"source": "source"}  # kind of file -> option
IN_FILE = {"voltage": "device.bias.voltage"}  # option -> where it sits in a file


def add_arguments(parser):
    parser.add_argument("det_name", help="Device project")
    parser.add_argument(
        "source",
        nargs="?",
        help="signal source or beam configuration",
    )
    parser.add_argument("-evt", "--events-per-job", type=int, help="events per job")
    parser.add_argument(
        "--edep-min", type=float, help="least energy deposited in the device [MeV]"
    )
    parser.add_argument(
        "--edep-max", type=float, help="most energy deposited in the device [MeV]"
    )
    parser.add_argument("--plots", type=int, help="draw the first N recorded events of each job")
    parser.add_argument("-vol", "--voltage", type=float, help="bias voltage")
    parser.add_argument("-irr", "--irradiation", type=float, help="irradiation flux")
    parser.add_argument(
        "-g4_vis", help="visualization of Geant4 experiment", action="store_true"
    )
    parser.add_argument(
        "--g4-vis-driver",
        default="OGL",
        help="Geant4 visualization driver of -g4_vis (default: OGL)",
    )
    parser.add_argument("-amp", "--amplifier", type=str, help="amplifier")


def job_command(kwargs):
    if kwargs.get("g4_vis"):
        return ["-g4_vis", "--g4-vis-driver", kwargs["g4_vis_driver"]]
    return []


def _deposits(kwargs):
    from . import gen_signal

    gen_signal.deposits(kwargs)


def _currents(kwargs):
    from . import gen_signal

    gen_signal.currents(kwargs)


def _waveforms(kwargs):
    from . import gen_signal

    gen_signal.waveforms(kwargs)


# A slice is named by the file it writes; its keys and kinds of file are what
# it reads and no slice before it does.
SLICES = (
    Slice(
        "deposits",
        _deposits,
        keys=("source", "g4setup", "events_per_job", "edep_min", "edep_max"),
        kinds=("source", "g4setup"),
    ),
    Slice("currents", _currents, keys=("voltage", "irradiation", "plots")),
    Slice("waveforms", _waveforms, keys=("amplifier",)),
)


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
    slices=SLICES,
    command=job_command,
)


def register(subparsers):
    parser = subparsers.add_parser("signal", help="single signal simulation")
    add_arguments(parser)
    WORKFLOW.attach(parser)
    parser.set_defaults(_project="det_name", _components=("signal",))
