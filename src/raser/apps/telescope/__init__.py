"""Telescope application package."""

import json
from pathlib import Path

from raser.lifecycle.slices import Slice
from raser.lifecycle.workflow import Workflow

TAICHU_V1 = json.loads((Path(__file__).parent / "telescope.json").read_text("utf-8"))


def _deposits(kwargs):
    from . import telescope_signal

    telescope_signal.deposits(kwargs)


def _currents(kwargs):
    from . import telescope_signal

    telescope_signal.currents(kwargs)


# The layers are the detectors of one deposits file; the currents are one
# file per layer.
SLICES = (
    Slice("deposits", _deposits, keys=("events_per_job", "solution")),
    Slice("currents", _currents),
)


def register(subparsers):
    parser = subparsers.add_parser("telescope", help="telescope")
    setups = parser.add_subparsers(dest="telescope_setup", required=True)
    for setup in ("taichu_v1", "taichu_v2", "acts_v1"):
        setup_parser = setups.add_parser(setup)
        command = None
        keys = ()
        job, slices = run, ()
        if setup == "taichu_v1":
            setup_parser.add_argument(
                "-evt", "--events-per-job", type=int, help="events per job"
            )
            setup_parser.add_argument(
                "--solution",
                choices=("full", "fast"),
                help="how the hits are found: Geant4 and diffusion, or straight "
                "tracks whose charge goes to the pixel under them; full by default",
            )
            keys = ("events_per_job", "solution")
            job, slices = None, SLICES
        if setup == "taichu_v2":
            setup_parser.add_argument("variant", nargs="?", default="taichu_v2")
            command = _variant
        Workflow(
            name=f"telescope {setup}",
            job=job,
            slices=slices,
            keys=keys,
            defaults={"events_per_job": TAICHU_V1["total_events"], "solution": "full"}
            if keys
            else {},
            device=False,
            command=command,
        ).attach(setup_parser)
    parser.set_defaults(_run=run, _components=("telescope",))


def _variant(kwargs):
    return [kwargs["variant"]]


def run(kwargs):
    setup = kwargs["telescope_setup"]
    if setup == "taichu_v2":
        from .telescope_signal import taichu_v2

        return taichu_v2(kwargs["variant"])
    from .telescope_acts import main

    return main(kwargs["seed"])
