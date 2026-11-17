"""
Description:  tct/__init__.py
@Date       : 2025
@Author     : Xin Shi, Chenxi Fu, Lin Zhu
@version    : 2.0
"""

import json
from pathlib import Path

from raser.lifecycle.slices import Slice
from raser.lifecycle.workflow import Workflow
from raser.stages import chain

DEFAULTS = json.loads(
    (Path(__file__).parent / "transient_current.json").read_text("utf-8")
)
KEYS = ("laser", "voltage", "amplifier")
COMPONENTS = {"laser": "laser"}  # kind of file -> option
IN_FILE = {"voltage": "device.bias.voltage"}  # option -> where it sits in a file


def register(subparsers):
    parser = subparsers.add_parser("tct", help="TCT simulation")
    parser.add_argument("det_name", help="name of the detector")
    parser.add_argument("laser", nargs="?", help="name of the laser")
    parser.add_argument("-vol", "--voltage", type=float, help="bias voltage")
    parser.add_argument("-amp", "--amplifier", type=str, help="amplifier")
    WORKFLOW.attach(parser)
    parser.set_defaults(_project="det_name")


def _currents(kwargs):
    from . import tct_signal

    tct_signal.currents(kwargs)


def _waveforms(kwargs):
    from . import tct_signal

    tct_signal.waveforms(kwargs)


WORKFLOW = Workflow(
    name="tct",
    keys=KEYS,
    defaults={"laser": DEFAULTS["laser"], **chain.READOUT_DEFAULTS},
    components=COMPONENTS,
    in_file=IN_FILE,
    slices=(
        Slice("currents", _currents, keys=("laser", "voltage"), kinds=("laser",)),
        Slice("waveforms", _waveforms, keys=("amplifier",), new_events=False),
    ),
    seeds=False,
)

