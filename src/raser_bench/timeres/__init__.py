"""Time-resolution experiment application."""

import json
from pathlib import Path

from raser.stages import chain

DEFAULTS = json.loads((Path(__file__).parent / "time_resolution.json").read_text("utf-8"))


class Timeres(chain.Chain):
    name = "timeres"
    help = "time-resolution experiment"
    components = ("raser_bench/timeres", "raser_bench/signal")
    defaults = {
        **{f"deposit.{key}": value for key, value in DEFAULTS.items()},
        "deposit.events_per_job": 10000,
        "deposit.plots": 0,
        "current.plots": 0,
    }


WORKFLOW = Timeres.workflow()
