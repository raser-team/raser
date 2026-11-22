"""
Description:  tct/__init__.py
@Date       : 2025
@Author     : Xin Shi, Chenxi Fu, Lin Zhu
@version    : 2.0
"""

import json
from pathlib import Path

from raser.lifecycle.experiment import Experiment
from raser.lifecycle.slices import Slice
from raser.lifecycle.workflow import Workflow
from raser.stages import chain

DEFAULTS = json.loads(
    (Path(__file__).parent / "transient_current.json").read_text("utf-8")
)
KEYS = ("laser", "voltage", "amplifier")
COMPONENTS = {"laser": "laser"}  # kind of file -> option
IN_FILE = {"voltage": "device.bias.voltage"}  # option -> where it sits in a file


def _currents(kwargs):
    from . import tct_signal

    tct_signal.currents(kwargs)


def _waveforms(kwargs):
    from . import tct_signal

    tct_signal.waveforms(kwargs)


class Tct(Experiment):
    name = "tct"
    help = "TCT simulation"
    stages = ("field", "current", "readout")

    @classmethod
    def arguments(cls, parser) -> None:
        parser.add_argument("det_name", help="name of the detector")
        parser.add_argument("laser", nargs="?", help="name of the laser")
        parser.add_argument("-vol", "--voltage", type=float, help="bias voltage")
        parser.add_argument("-amp", "--amplifier", type=str, help="amplifier")

    @classmethod
    def build(cls) -> Workflow:
        return Workflow(
            name=cls.name,
            keys=KEYS,
            defaults={
                "laser": DEFAULTS["laser"],
                "amplifier": chain.DEFAULTS["readout.amplifier"],
                "sheet_resistance": None,
            },
            components=COMPONENTS,
            in_file=IN_FILE,
            slices=(
                Slice(
                    "current", _currents, keys=("laser", "voltage"), kinds=("laser",)
                ),
                Slice("readout", _waveforms, keys=("amplifier",), new_events=False),
            ),
            seeds=False,
        )


WORKFLOW = Tct.workflow()
