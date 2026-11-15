"""Telescope application package."""

import json
from pathlib import Path

from raser.lifecycle.workflow import Workflow

TAICHU_V1 = json.loads((Path(__file__).parent / "telescope.json").read_text("utf-8"))


def register(subparsers):
    parser = subparsers.add_parser("telescope", help="telescope")
    setups = parser.add_subparsers(dest="telescope_setup", required=True)
    for setup in ("taichu_v1", "taichu_v2", "acts_v1", "g4"):
        setup_parser = setups.add_parser(setup)
        command = None
        keys = ()
        if setup == "taichu_v1":
            setup_parser.add_argument(
                "-evt", "--events-per-job", type=int, help="events per job"
            )
            keys = ("events_per_job",)
        if setup == "taichu_v2":
            setup_parser.add_argument("variant", nargs="?", default="taichu_v2")
            command = _variant
        Workflow(
            name=f"telescope {setup}",
            job=run,
            keys=keys,
            defaults={key: TAICHU_V1["total_events"] for key in keys},
            device=False,
            command=command,
        ).attach(setup_parser)
    parser.set_defaults(_run=run, _components=("telescope",))


def _variant(kwargs):
    return [kwargs["variant"]]


def run(kwargs):
    setup = kwargs["telescope_setup"]
    if setup == "taichu_v1":
        from .telescope_signal import main

        return main(kwargs["seed"], kwargs["events_per_job"])
    if setup == "taichu_v2":
        from .telescope_signal import taichu_v2

        return taichu_v2(kwargs["variant"])
    if setup == "acts_v1":
        from .telescope_acts import main

        return main(kwargs["seed"])
    from .telescope_g4 import main

    return main()
