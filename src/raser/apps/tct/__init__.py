"""
Description:  tct/__init__.py
@Date       : 2025
@Author     : Xin Shi, Chenxi Fu, Lin Zhu
@version    : 2.0
"""

import json
from pathlib import Path

from raser.lifecycle.workflow import Workflow

DEFAULTS = json.loads(
    (Path(__file__).parent / "transient_current.json").read_text("utf-8")
)
KEYS = ("laser", "voltage", "amplifier")
COMPONENTS = {"laser": "laser", "afe": "amplifier"}  # kind of file -> option
IN_FILE = {"voltage": "device.bias.voltage"}  # option -> where it sits in a file


def _add_arguments(parser):
    parser.add_argument("det_name", help="name of the detector")
    parser.add_argument("laser", nargs="?", help="name of the laser")
    parser.add_argument("-vol", "--voltage", type=float, help="bias voltage")
    parser.add_argument("-amp", "--amplifier", type=str, help="amplifier")


def register(subparsers):
    parser = subparsers.add_parser("tct", help="TCT simulation")
    modes = parser.add_subparsers(dest="tct_mode", required=True)
    parser.set_defaults(_project="det_name")

    signal = modes.add_parser("signal", help="TCT signal")
    _add_arguments(signal)
    SIGNAL.attach(signal)

    position_signal = modes.add_parser("position_signal", help="TCT position signal")
    _add_arguments(position_signal)
    POSITION_SIGNAL.attach(position_signal)

    position_scan_draw = modes.add_parser(
        "position_scan_draw", help="draw TCT position scan"
    )
    position_scan_draw.add_argument("det_name", help="name of the detector")
    position_scan_draw.add_argument("laser", help="name of the laser")
    position_scan_draw.set_defaults(_run=run_position_scan_draw)


def _signal_job(kwargs):
    from . import tct_signal

    tct_signal.main(kwargs)


def _position_signal_job(kwargs):
    from . import tct_signal_position_scan

    if kwargs.get("job_index") is None:
        kwargs["job_index"] = 0
    tct_signal_position_scan.job_main(kwargs)


SIGNAL = Workflow(
    name="tct signal",
    keys=KEYS,
    defaults={"amplifier": DEFAULTS["amplifier"]},
    components=COMPONENTS,
    in_file=IN_FILE,
    job=_signal_job,
    seeds=False,
)
POSITION_SIGNAL = Workflow(
    name="tct position_signal",
    keys=KEYS,
    defaults={"amplifier": DEFAULTS["amplifier"]},
    components=COMPONENTS,
    in_file=IN_FILE,
    job=_position_signal_job,
)


def run_position_scan_draw(kwargs):
    from . import tct_signal_position_scan_draw

    tct_signal_position_scan_draw.main(kwargs)
